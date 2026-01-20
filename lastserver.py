import httpx
from fastapi import FastAPI, Request, Response

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

# Your unmodified MCP server (main.py)
MCP_UPSTREAM = "http://127.0.0.1:8000/mcp"  # ← main.py port

app = FastAPI()

# 🔑 SINGLE GLOBAL MCP SESSION (REQUIRED FOR AGENT BUILDER)
SESSION_ID = None


# ─────────────────────────────────────────────
# MCP BRIDGE (AGENT BUILDER SAFE)
# ─────────────────────────────────────────────
@app.api_route("/mcp", methods=["POST"])
async def mcp_bridge(request: Request):
    global SESSION_ID

    # 🚫 DO NOT PARSE
    # 🚫 DO NOT MODIFY
    # 🚫 DO NOT INSPECT
    body = await request.body()

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    # ✅ Force ALL requests into the same MCP session
    if SESSION_ID:
        headers["mcp-session-id"] = SESSION_ID

    async with httpx.AsyncClient(timeout=None) as client:
        upstream = await client.post(
            MCP_UPSTREAM,
            content=body,   # RAW BYTES ONLY
            headers=headers,
        )

    # ✅ Capture MCP session ONCE (initialize)
    if "mcp-session-id" in upstream.headers and SESSION_ID is None:
        SESSION_ID = upstream.headers["mcp-session-id"]

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers={
            "Content-Type": upstream.headers.get(
                "content-type", "application/json"
            ),
            **({"mcp-session-id": SESSION_ID} if SESSION_ID else {}),
        },
    )


# ─────────────────────────────────────────────
# CHAT ENDPOINT (FRONTEND → AGENT BUILDER)
# ─────────────────────────────────────────────
@app.post("/api/chat")
async def chat_proxy(request: Request):
    payload = await request.json()
    return {"status": "ok", "echo": payload}


# ─────────────────────────────────────────────
# HEALTH
# ─────────────────────────────────────────────
@app.get("/")
def health():
    return {"status": "ok"}


# ─────────────────────────────────────────────
# START
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
