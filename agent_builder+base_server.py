#WORKS!
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
import uuid

MCP_UPSTREAM = "http://127.0.0.1:8080/mcp"

app = FastAPI()

# Simple in-memory session map
# Agent Builder has no real session concept, so we fake one
SESSION_ID = None


@app.api_route("/mcp", methods=["POST"])
async def mcp_bridge(request: Request):
    global SESSION_ID

    body = await request.body()

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    # Attach MCP session if we have one
    if SESSION_ID:
        headers["mcp-session-id"] = SESSION_ID

    async with httpx.AsyncClient(timeout=None) as client:
        upstream = await client.post(
            MCP_UPSTREAM,
            content=body,
            headers=headers,
        )

    # Capture session on initialize
    if "mcp-session-id" in upstream.headers:
        SESSION_ID = upstream.headers["mcp-session-id"]

    def stream():
        yield upstream.content

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers={
            "Content-Type": upstream.headers.get(
                "content-type", "application/json"
            ),
            **(
                {"mcp-session-id": SESSION_ID}
                if SESSION_ID
                else {}
            ),
        },
    )
