import os, asyncio, json, httpx, logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.sse import SseServerTransport
import mcp.types as types

# Setup logging so we can see exactly what OpenAI is doing
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-bridge")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["mcp-session-id"],
)

@app.middleware("http")
async def add_ngrok_skip_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response

# Initialize the server with EXPLICIT capabilities
mcp_server = Server("Workspace-Bridge")

# --- TOOL DEFINITIONS ---
@mcp_server.list_tools()
async def handle_list_tools():
    logger.info("📬 OpenAI is now fetching the tool list!")
    return [
        types.Tool(
            name="search_gmail_messages",
            description="Search for emails in Gmail",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"]
            }
        )
    ]

@mcp_server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    logger.info(f"⚡ OpenAI is executing: {name}")
    # Simple mock response for testing - once this works, we link back to 8080
    return [types.TextContent(type="text", text="Tool execution successful!")]

# --- SSE TRANSPORT ---
sse_transport = SseServerTransport("/messages")

@app.get("/")
async def root():
    return HTMLResponse("<h1>Bridge is Online</h1><p>Connect OpenAI to <code>/sse</code></p>")

@app.api_route("/sse", methods=["GET", "POST"])
async def handle_sse(request: Request):
    logger.info(f"📡 Connection attempt on /sse [{request.method}]")
    if request.method == "POST":
        return JSONResponse({"status": "ready"})
    
    async with sse_transport.connect_sse(request.scope, request.receive, request._send) as (read_stream, write_stream):
        # We pass explicit initialization options here
        init_options = mcp_server.create_initialization_options()
        # ENSURE TOOLS CAPABILITY IS ADVERTISED
        init_options.capabilities.tools = {} 
        
        await mcp_server.run(read_stream, write_stream, init_options)

@app.post("/messages")
async def handle_messages(request: Request):
    logger.info("📩 Message received from OpenAI")
    await sse_transport.handle_post_message(request.scope, request.receive, request._send)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)