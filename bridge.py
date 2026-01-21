# bridge.py
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
import logging

# CONFIGURATION
# Set this to the port main.py is actually running on
MCP_UPSTREAM_URL = "http://127.0.0.1:8000/mcp" 

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bridge")

# The "Golden Session" - shared by all Agent Builder requests
SESSION_ID = None

@app.api_route("/mcp", methods=["GET", "POST"])
async def mcp_bridge(request: Request):
    global SESSION_ID

    method = request.method
    params = request.query_params
    body = await request.body()
    
    # 1. Prepare headers for the real MCP server
    headers = dict(request.headers)
    # Remove 'host' to avoid proxy confusion
    headers.pop("host", None)
    
    # 2. If we have a pinned session, force it
    if SESSION_ID:
        headers["mcp-session-id"] = SESSION_ID
        logger.info(f"Using pinned session: {SESSION_ID}")

    async with httpx.AsyncClient(timeout=None) as client:
        if method == "GET":
            # Handle the SSE Stream
            async def stream_generator():
                async with client.stream("GET", MCP_UPSTREAM_URL, params=params, headers=headers) as resp:
                    # Capture session ID if it's the first time
                    process_session_id(resp.headers)
                    async for line in resp.aiter_lines():
                        yield f"{line}\n"

            return StreamingResponse(stream_generator(), media_type="text/event-stream")
        
        else:
            # Handle Tool Calls/Initialize (POST)
            resp = await client.post(MCP_UPSTREAM_URL, content=body, headers=headers)
            process_session_id(resp.headers)
            
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers={"mcp-session-id": SESSION_ID} if SESSION_ID else {}
            )

def process_session_id(headers):
    global SESSION_ID
    if "mcp-session-id" in headers:
        if SESSION_ID is None:
            SESSION_ID = headers["mcp-session-id"]
            logger.info(f"🌟 Captured NEW Session ID: {SESSION_ID}")
        elif SESSION_ID != headers["mcp-session-id"]:
            logger.info(f"Overriding upstream session {headers['mcp-session-id']} with pinned {SESSION_ID}")

if __name__ == "__main__":
    import uvicorn
    # Run the bridge on a different port than main.py
    uvicorn.run(app, host="0.0.0.0", port=8050)