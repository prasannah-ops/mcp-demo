#WORKS!
import os
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent

load_dotenv()

# --- PASTE YOUR MODEL ID OR LINK HERE ---
# This is the only place you need to change the model.
CURRENT_MODEL = "google/gemini-2.0-flash-exp"
# ----------------------------------------

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# 1. Setup the MCP Server
mcp_server = Server("openrouter-bridge")

@mcp_server.list_tools()
async def handle_list_tools():
    """This is the function that Agent Builder calls to 'find' your tool."""
    return [
        Tool(
            name="call_llm",
            description="Executes the user's request using the currently active LLM.",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "The user's question or task."}
                },
                "required": ["prompt"]
            }
        )
    ]

@mcp_server.call_tool()
async def handle_call_tool(name, arguments):
    if name == "call_llm":
        prompt = arguments.get("prompt")
        
        # Strip URL if you pasted a full link into CURRENT_MODEL
        model_id = CURRENT_MODEL.replace("https://openrouter.ai/", "").strip("/")
        
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": model_id,
                "messages": [{"role": "user", "content": prompt}]
            }
        )
        
        data = response.json()
        if "choices" in data:
            result = data['choices'][0]['message']['content']
        else:
            result = f"Error: {str(data)}"
            
        return [TextContent(type="text", text=result)]

# 2. Setup FastAPI with the separate endpoints that worked for discovery
app = FastAPI()
sse_transport = SseServerTransport("/messages")

@app.get("/sse")
async def handle_sse(request: Request):
    """The endpoint you enter into Agent Builder."""
    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as (read_stream, write_stream):
        await mcp_server.run(
            read_stream,
            write_stream,
            mcp_server.create_initialization_options()
        )

@app.post("/messages")
async def handle_messages(request: Request):
    """The endpoint the Agent calls to execute the tool."""
    await sse_transport.handle_post_message(request.scope, request.receive, request._send)
    # Returning an empty Response prevents the 'Unexpected ASGI message' error
    return Response()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)