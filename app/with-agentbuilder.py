# server.py
# ======================================================
# SINGLE-BRAIN AGENT SERVER
#
# - OpenRouter is the ONLY LLM
# - Model is defined HERE
# - Google MCP (main.py) is TOOLS ONLY
# - Agent Builder talks to /mcp but never thinks
# - index.html is just a UI
# ======================================================

import sys, json, httpx
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, Response
from dotenv import dotenv_values

# ======================================================
# 🔐 ENV
# ======================================================
env = dotenv_values(".env")

OPENROUTER_KEY = env.get("OPENROUTER_API_KEY")
USER_EMAIL = env.get("USER_GOOGLE_EMAIL")

if not OPENROUTER_KEY:
    print("❌ OPENROUTER_API_KEY missing")
    sys.exit(1)

print("✅ Using OpenRouter key:", OPENROUTER_KEY[:10], "...")

# ======================================================
# ⚙️ CONFIG
# ======================================================
OR_URL = "https://openrouter.ai/api/v1/chat/completions"

# 🔴 DEFINE YOUR MODEL HERE (AUTHORITATIVE)
MODEL = "anthropic/claude-3.5-sonnet"

OR_HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "http://localhost:8081",
    "X-Title": "SINGLE_BRAIN_AGENT",
}

# Google MCP backend (main.py)
MCP_URL = "http://127.0.0.1:8080/mcp"
MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

# ======================================================
# 🚀 APP
# ======================================================
app = FastAPI()

CHAT_HISTORY = []
MCP_SESSION_ID = None

# ======================================================
# 🧠 SYSTEM PROMPT
# ======================================================
def system_prompt():
    return (
        f"You are an AI assistant.\n"
        f"Date: {datetime.now().strftime('%Y-%m-%d')}\n"
        f"User email: {USER_EMAIL}\n"
        f"You may call tools when useful."
    )

# ======================================================
# 🔄 MCP SESSION
# ======================================================
async def ensure_mcp_session():
    global MCP_SESSION_ID

    if MCP_SESSION_ID:
        return MCP_SESSION_ID

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
                    "clientInfo": {"name": "single-brain", "version": "1.0"},
                },
            },
        )

        MCP_SESSION_ID = init.headers.get("mcp-session-id")

        await client.post(
            MCP_URL,
            headers={**MCP_HEADERS, "mcp-session-id": MCP_SESSION_ID},
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )

    return MCP_SESSION_ID

# ======================================================
# 🧰 MCP CALL
# ======================================================
async def call_mcp(method, params=None):
    session = await ensure_mcp_session()

    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "POST",
            MCP_URL,
            headers={**MCP_HEADERS, "mcp-session-id": session},
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": method,
                "params": params or {},
            },
        ) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data:"):
                    return json.loads(line.removeprefix("data: ").strip())

    return {}

# ======================================================
# 🌐 UI
# ======================================================
@app.get("/", response_class=HTMLResponse)
async def index():
    return open("index.html").read()

# ======================================================
# 💬 CHAT ENDPOINT (OPENROUTER THINKS)
# ======================================================
@app.post("/api/chat")
async def chat(req: Request):
    global CHAT_HISTORY
    body = await req.json()
    user_msg = body.get("message")

    if not CHAT_HISTORY:
        CHAT_HISTORY.append({"role": "system", "content": system_prompt()})

    CHAT_HISTORY.append({"role": "user", "content": user_msg})

    async def stream():
        global CHAT_HISTORY
        final_text = ""

        try:
            # 1️⃣ Load MCP tools
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

            tool_map = {
                t["name"].replace(".", "_"): t["name"]
                for t in tools
            }

            async with httpx.AsyncClient(timeout=60) as client:
                # 2️⃣ Reasoning loop
                while True:
                    payload = {
                        "model": MODEL,
                        "messages": CHAT_HISTORY,
                        "tools": llm_tools or None,
                        "max_tokens": 1000,
                    }

                    res = await client.post(
                        OR_URL, headers=OR_HEADERS, json=payload
                    )
                    res.raise_for_status()

                    msg = res.json()["choices"][0]["message"]

                    if not msg.get("tool_calls"):
                        break

                    CHAT_HISTORY.append(msg)

                    for tc in msg["tool_calls"]:
                        tool_name = tool_map[tc["function"]["name"]]
                        args = json.loads(tc["function"]["arguments"])

                        tool_res = await call_mcp(
                            "tools/call",
                            {"name": tool_name, "arguments": args},
                        )

                        CHAT_HISTORY.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": str(tool_res),
                        })

                # 3️⃣ Final stream
                payload["stream"] = True
                payload["messages"] = CHAT_HISTORY

                async with client.stream(
                    "POST", OR_URL, headers=OR_HEADERS, json=payload
                ) as resp:
                    async for line in resp.aiter_lines():
                        if line == "data: [DONE]":
                            break
                        if line.startswith("data: "):
                            chunk = json.loads(line[6:])
                            token = chunk["choices"][0]["delta"].get("content")
                            if token:
                                final_text += token
                                yield token

                CHAT_HISTORY.append(
                    {"role": "assistant", "content": final_text}
                )

        except Exception as e:
            yield f"\n[ERROR] {str(e)}"

    return StreamingResponse(stream(), media_type="text/plain")

# ======================================================
# 🤖 MCP ENDPOINT (AGENT BUILDER)
# ======================================================
@app.post("/mcp")
async def mcp_proxy(req: Request):
    body = await req.body()

    headers = {
        "Content-Type": req.headers.get("content-type", "application/json"),
        "Accept": req.headers.get("accept", "application/json"),
    }

    if "mcp-session-id" in req.headers:
        headers["mcp-session-id"] = req.headers["mcp-session-id"]

    async with httpx.AsyncClient(timeout=None) as client:
        upstream = await client.post(MCP_URL, content=body, headers=headers)

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers={
            "Content-Type": upstream.headers.get("content-type", "application/json"),
            **(
                {"mcp-session-id": upstream.headers["mcp-session-id"]}
                if "mcp-session-id" in upstream.headers
                else {}
            ),
        },
    )

# ======================================================
# ▶️ RUN
# ======================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
