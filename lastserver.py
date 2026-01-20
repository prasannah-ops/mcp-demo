import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

# Agent Builder MCP endpoint (THIS is the agent)
AGENT_BUILDER_URL = "http://127.0.0.1:3000/mcp"

# This server (UI gateway)
PORT = 8081

app = FastAPI()

# Agent Builder manages session state
SESSION_ID = None


# ─────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("app/index.html", "r") as f:
        return f.read()


# ─────────────────────────────────────────────
# CHAT → AGENT BUILDER
# ─────────────────────────────────────────────

@app.post("/api/chat")
async def chat(request: Request):
    """
    Receives user input from frontend
    Forwards it to Agent Builder
    Streams Agent Builder output back to frontend
    """
    global SESSION_ID

    body = await request.json()
    user_message = body.get("message", "")

    # Agent Builder expects MCP-style messages
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "agent/run",
        "params": {
            "input": user_message
        }
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    if SESSION_ID:
        headers["mcp-session-id"] = SESSION_ID

    async def stream():
        global SESSION_ID

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                AGENT_BUILDER_URL,
                headers=headers,
                json=payload,
            ) as resp:

                # Capture session ID if Agent Builder assigns one
                if "mcp-session-id" in resp.headers:
                    SESSION_ID = resp.headers["mcp-session-id"]

                async for line in resp.aiter_lines():
                    if not line:
                        continue

                    # Agent Builder streams via SSE
                    if line.startswith("data:"):
                        data = line.removeprefix("data:").strip()
                        if data == "[DONE]":
                            break
                        yield data

    return StreamingResponse(stream(), media_type="text/plain")


# ─────────────────────────────────────────────
# START
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
