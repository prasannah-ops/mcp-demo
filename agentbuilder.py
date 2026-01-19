#no openrouter
#doesnt work yet
import os, asyncio, json, httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from dotenv import dotenv_values
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.sse import SseServerTransport

# --- CONFIG ---
env_config = dotenv_values(".env")
TARGET_EMAIL = env_config.get("USER_GOOGLE_EMAIL", "prasannah@aiatcore.com")
MCP_URL_8080 = "http://127.0.0.1:8080/mcp"

app = FastAPI()

@app.middleware("http")
async def add_ngrok_skip_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response

async def call_8080_raw(method, params=None):
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    async with httpx.AsyncClient(timeout=None) as client:
        init_resp = await client.post(MCP_URL_8080, headers=headers, json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-10-07", "capabilities": {}, 
                       "clientInfo": {"name": "bridge", "version": "1.0"}}
        })
        session_id = init_resp.headers["mcp-session-id"]
        await client.post(MCP_URL_8080, headers={**headers, "mcp-session-id": session_id},
                          json={"jsonrpc": "2.0", "method": "notifications/initialized"})
        async with client.stream("POST", MCP_URL_8080, headers={**headers, "mcp-session-id": session_id},
                                 json={"jsonrpc": "2.0", "id": 2, "method": method, "params": params or {}}) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data:"):
                    payload = line.removeprefix("data:").strip()
                    return json.loads(payload)
    return None

mcp_server = Server("Direct-Bridge")

@mcp_server.list_tools()
async def handle_list_tools():
    return [
        Tool(
            name="execute_task",
            description="Executes Gmail or file tasks.",
            inputSchema={
                "type": "object",
                "properties": {
                    # RENAMED TO MATCH AGENT OUTPUT
                    "reply": {"type": "string"} 
                },
                "required": ["reply"]
            }
        )
    ]

@mcp_server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    # USE THE NEW KEY
    query_text = arguments.get("reply") 
    print(f"🛠️ OpenAI is requesting: {query_text}")

    result = await call_8080_raw("tools/call", {
        "name": "search_gmail_messages", 
        "arguments": {
            "query": query_text, 
            "user_google_email": TARGET_EMAIL
        }
    })

    try:
        content = result['result']['content'][0]['text']
        return [TextContent(type="text", text=str(content))]
    except:
        return [TextContent(type="text", text=json.dumps(result))]

sse_transport = SseServerTransport("/messages")

@app.api_route("/sse", methods=["GET", "POST"])
async def handle_sse(request: Request):
    if request.method == "POST": return JSONResponse({"status": "ready"})
    async with sse_transport.connect_sse(request.scope, request.receive, request._send) as (read_stream, write_stream):
        await mcp_server.run(read_stream, write_stream, mcp_server.create_initialization_options())

@app.post("/messages")
async def handle_messages(request: Request):
    await sse_transport.handle_post_message(request.scope, request.receive, request._send)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)