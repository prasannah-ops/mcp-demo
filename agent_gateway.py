#WORKS!
import json
import httpx
from fastapi import FastAPI, Request, Response
from dotenv import dotenv_values

# ─────────────────────────────────────────────
# ENV
# ─────────────────────────────────────────────
env = dotenv_values(".env")
OR_KEY = env.get("OPENROUTER_API_KEY")

OR_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "anthropic/claude-3.5-sonnet"

# Your Google Workspace MCP (main.py)
MCP_UPSTREAM = "http://127.0.0.1:8080/mcp"

app = FastAPI()

# Agent Builder has no session concept → we fake one
SESSION_ID = None


# ─────────────────────────────────────────────
# MCP BRIDGE (THIS IS WHAT AGENT BUILDER NEEDS)
# ─────────────────────────────────────────────
@app.api_route("/mcp", methods=["POST"])
async def mcp_bridge(request: Request):
    global SESSION_ID

    body = await request.body()

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    if SESSION_ID:
        headers["mcp-session-id"] = SESSION_ID

    async with httpx.AsyncClient(timeout=None) as client:
        upstream = await client.post(
            MCP_UPSTREAM,
            content=body,
            headers=headers,
        )

    # Capture MCP session on initialize
    if "mcp-session-id" in upstream.headers:
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
# OPTIONAL: health check (for ngrok testing)
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
