
#WORKS!
import os, asyncio, json, httpx, sys
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from dotenv import dotenv_values # Use this instead of load_dotenv

# --- STEP 1: MANUAL KEY EXTRACTION (BYPASS OS) ---
# We read the .env file like a normal text file to ensure NO system override
env_config = dotenv_values(".env")

# Assign specifically to unique variable names to avoid OS collisions
SUPERVISOR_OR_KEY = env_config.get("OPENROUTER_API_KEY")
TARGET_EMAIL = env_config.get("USER_GOOGLE_EMAIL")

if SUPERVISOR_OR_KEY:
    print(f"--- 🛡️ HARDWARE-LEVEL KEY CHECK ---")
    print(f"KEY LOADED FROM FILE: {SUPERVISOR_OR_KEY[:12]}...")
    print(f"TARGET EMAIL: {TARGET_EMAIL}")
    print(f"----------------------------------")
else:
    print("❌ CRITICAL: KEY NOT FOUND IN .ENV FILE")
    sys.exit(1)

app = FastAPI()

# --- CONFIG ---
OR_URL = "https://openrouter.ai/api/v1/chat/completions"
# Use a specific label to identify this in the dashboard
OR_HEADERS = {
    "Authorization": f"Bearer {SUPERVISOR_OR_KEY}",
    "HTTP-Referer": "http://localhost:8081",
    "X-Title": "SUPERVISOR_SESSION_TEST", 
    "Content-Type": "application/json"
}

# Guaranteed OpenRouter model for testing
MODEL = "" 

MCP_URL = "http://127.0.0.1:8080/mcp"
SESSION_ID = None
MCP_HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
CHAT_HISTORY = []

def get_system_prompt():
    now = datetime.now()
    return f"Assistant. Running on OpenRouter. Date: {now.strftime('%Y-%m-%d')}. Email: {TARGET_EMAIL}."

# --- MCP HANDSHAKE (Standard) ---
async def ensure_mcp_session():
    global SESSION_ID
    if SESSION_ID: return SESSION_ID
    async with httpx.AsyncClient(timeout=None) as client:
        init_resp = await client.post(MCP_URL, headers=MCP_HEADERS, json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-10-07", "capabilities": {},
            "clientInfo": {"name": "orchestrator", "version": "1.0.0"}},
        })
        SESSION_ID = init_resp.headers.get("mcp-session-id")
        await client.post(MCP_URL, headers={**MCP_HEADERS, "mcp-session-id": SESSION_ID},
            json={"jsonrpc": "2.0", "method": "notifications/initialized"})
        return SESSION_ID

async def call_mcp(method, params=None):
    session_id = await ensure_mcp_session()
    async with httpx.AsyncClient(timeout=None) as client:
        try:
            async with client.stream("POST", MCP_URL, headers={**MCP_HEADERS, "mcp-session-id": session_id}, 
                json={"jsonrpc": "2.0", "id": 2, "method": method, "params": params or {}}) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data:"):
                        return json.loads(line.removeprefix("data:").strip())
        except Exception as e:
            return {"error": {"message": str(e)}}

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("index.html", "r") as f: return f.read()

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
        full_ai_response = ""
        try:
            # 1. Setup Tools
            tools_res = await call_mcp("tools/list")
            mcp_tools = tools_res.get('result', {}).get('tools', [])
            llm_tools = [{"type": "function", "function": {"name": t['name'].replace('.', '_'), "description": t['description'], "parameters": t['inputSchema']}} for t in mcp_tools]
            tool_name_map = {t['name'].replace('.', '_'): t['name'] for t in mcp_tools}

            # 2. Reasoning Loop
            async with httpx.AsyncClient(timeout=60.0) as client:
                while True:
                    payload = {
                        "model": MODEL,
                        "messages": CHAT_HISTORY,
                        "tools": llm_tools if llm_tools else None,
                        "max_tokens": 1000 # Keep reservation low to avoid 402
                    }
                    
                    print(f"📡 OUTGOING TO OPENROUTER...")
                    res = await client.post(OR_URL, headers=OR_HEADERS, json=payload)
                    
                    if res.status_code == 402:
                        yield f"Error 402: The supervisor key used ({SUPERVISOR_OR_KEY[:8]}...) has no credit assigned to this project."
                        return

                    res.raise_for_status()
                    ai_msg = res.json()['choices'][0]['message']
                    
                    if not ai_msg.get('tool_calls'):
                        break 

                    CHAT_HISTORY.append(ai_msg)
                    for t in ai_msg['tool_calls']:
                        mcp_name = tool_name_map.get(t['function']['name'], t['function']['name'])
                        tool_res = await call_mcp("tools/call", {"name": mcp_name, "arguments": json.loads(t['function']['arguments'])})
                        content_str = str(tool_res.get('result', {}).get('content', tool_res))
                        CHAT_HISTORY.append({"role": "tool", "tool_call_id": t['id'], "content": content_str})

                # 3. Final Stream
                payload["stream"] = True
                payload["messages"] = CHAT_HISTORY
                async with client.stream("POST", OR_URL, headers=OR_HEADERS, json=payload) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            if line == "data: [DONE]": break
                            try:
                                chunk = json.loads(line.removeprefix("data: "))
                                token = chunk['choices'][0]['delta'].get('content', '')
                                if token:
                                    full_ai_response += token
                                    yield token
                            except: continue

                CHAT_HISTORY.append({"role": "assistant", "content": full_ai_response})
        except Exception as e:
            yield f"\n[Error]: {str(e)}"

    return StreamingResponse(stream(), media_type="text/plain")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)