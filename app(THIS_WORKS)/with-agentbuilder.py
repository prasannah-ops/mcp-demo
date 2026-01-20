# server.py
# SINGLE-BRAIN SERVER:
# - /api/chat  -> Your app (OpenRouter + MCP tools)
# - /mcp       -> Agent Builder MCP endpoint
# - Uses Google MCP (main.py) as tool backend

import os, sys, json, httpx, asyncio
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, Response
from dotenv import dotenv_values

# =========================
# 🔐 ENV LOADING (HARD)
# =========================
env_config = dotenv_values(".env")

SUPERVISOR_OR_KEY = env_config.get("OPENROUTER_API_KEY")
TARGET_EMAIL = env_config.get("USER_GOOGLE_EMAIL")

if not SUPERVISOR_OR_KEY:
    print("❌ OPENROUTER_API_KEY missing from .env")
    sys.exit(1)

print("✅ Server booting with OpenRouter key:", SUPERVISOR_OR_KEY[:10], "...")

# =========================
# 🚀 APP
# =========================
app = FastAPI()

# =========================
# 🔗 CONFIG
# =========================
OR_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = ""  # keep empty or set explicitly

OR_HEADERS = {
    "Authorization": f"Bearer {SUPERVISOR_OR_KEY}",
    "HTTP-Referer": "http://localhost:8081",
    "X-Title": "APP_WITH_AGENT_BUILDER",
    "Content-Type": "application/json",
}

# Google MCP (main.py)
MCP_URL = "http://127.0.0.1:3000/mcp"
MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

SESSION_ID = None
CHAT_HISTORY = []

# =========================
# 🧠 SYSTEM PROMPT
# =========================
def get_system_prompt():
    now = datetime.now().strftime("%Y-%m-%d")
    return f"Assistant. Date: {now}. User email: {TARGET_EMAIL}."

# =========================
# 🔄 MCP SESSION HANDSHAKE
# =========================
async def ensure_mcp_session():
    global SESSION_ID

    if SESSION_ID:
        return SESSION_ID

    async with httpx.AsyncClient(timeout=None) as client:
        init = await client.post(
            MCP_URL,
            headers=MCP_HEADERS,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-10-07",
                    "capabilities": {},
                    "clientInfo": {"name": "app-server", "version": "1.0.0"},
                },
            },
        )

        SESSION_ID = init.headers.get("mcp-session-id")

        await client.post(
            MCP_URL,
            headers={**MCP_HEADERS, "mcp-session-id": SESSION_ID},
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )

    return SESSION_ID

# =========================
# 🧰 MCP CALL WRAPPER
# =========================
async def call_mcp(method, params=None):
    session_id = await ensure_mcp_session()

    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "POST",
            MCP_URL,
            headers={**MCP_HEADERS, "mcp-session-id": session_id},
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": method,
                "params": params or {},
            },
        ) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data:"):
                    return json.loads(line.removeprefix("data:").strip())

    return {"error": "No MCP response"}

# =========================
# 🌐 FRONTEND
# =========================
@app.get("/", response_class=HTMLResponse)
async def index():
    with open("index.html", "r") as f:
        return f.read()

# =========================
# 💬 APP CHAT ENDPOINT
# =========================
@app.post("/api/chat")
async def chat(request: Request):
    global CHAT_HISTORY
    data = await request.json()
    user_msg = data.get("message")

    if not CHAT_HISTORY:
        CHAT_HISTORY.append({"role": "system", "content": get_system_prompt()})

    CHAT_HISTORY.append({"role": "user", "content": user_msg})

    async def stream():
        global CHAT_HISTORY
        full_response = ""

        try:
            # 1️⃣ Get tools from MCP
            tools_res = await call_mcp("tools/list")
            tools = tools_res.get("result", {}).get("tools", [])

            llm_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"].replace(".", "_"),
                        "description": t["description"],
                        "parameters": t["inputSchema"],
                    },
                }
                for t in tools
            ]

            tool_map = {t["name"].replace(".", "_"): t["name"] for t in tools}

            async with httpx.AsyncClient(timeout=60) as client:
                while True:
                    payload = {
                        "model": MODEL,
                        "messages": CHAT_HISTORY,
                        "tools": llm_tools if llm_tools else None,
                        "max_tokens": 1000,
                    }

                    res = await client.post(OR_URL, headers=OR_HEADERS, json=payload)
                    res.raise_for_status()

                    msg = res.json()["choices"][0]["message"]

                    if not msg.get("tool_calls"):
                        break

                    CHAT_HISTORY.append(msg)

                    for tc in msg["tool_calls"]:
                        mcp_name = tool_map.get(tc["function"]["name"])
                        args = json.loads(tc["function"]["arguments"])

                        tool_res = await call_mcp(
                            "tools/call",
                            {"name": mcp_name, "arguments": args},
                        )

                        CHAT_HISTORY.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": str(tool_res),
                            }
                        )

                # 2️⃣ Final streaming response
                payload["stream"] = True
                payload["messages"] = CHAT_HISTORY

                async with client.stream(
                    "POST", OR_URL, headers=OR_HEADERS, json=payload
                ) as resp:
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            if line == "data: [DONE]":
                                break
                            chunk = json.loads(line.removeprefix("data: "))
                            token = chunk["choices"][0]["delta"].get("content")
                            if token:
                                full_response += token
                                yield token

                CHAT_HISTORY.append(
                    {"role": "assistant", "content": full_response}
                )

        except Exception as e:
            yield f"\n[ERROR]: {str(e)}"

    return StreamingResponse(stream(), media_type="text/plain")

# =========================
# 🤖 MCP ENDPOINT (AGENT BUILDER)
# =========================
@app.api_route("/mcp", methods=["POST"])
async def mcp_proxy(request: Request):
    body = await request.body()

    headers = {
        "Content-Type": request.headers.get("content-type", "application/json"),
        "Accept": request.headers.get("accept", "application/json"),
    }

    if "mcp-session-id" in request.headers:
        headers["mcp-session-id"] = request.headers["mcp-session-id"]

    async with httpx.AsyncClient(timeout=None) as client:
        upstream = await client.post(
            MCP_URL,
            content=body,
            headers=headers,
        )

    response_headers = {
        "Content-Type": upstream.headers.get("content-type", "application/json")
    }

    if upstream.headers.get("mcp-session-id"):
        response_headers["mcp-session-id"] = upstream.headers["mcp-session-id"]

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
    )

# =========================
# ▶️ RUN
# =========================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8081)
