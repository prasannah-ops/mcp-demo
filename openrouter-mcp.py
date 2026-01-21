# openrouter_mcp.py
import os, json, httpx
from fastmcp import FastMCP
import os
from dotenv import load_dotenv

load_dotenv()

OR_KEY = os.environ["OPENROUTER_API_KEY"]
OR_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openai/gtp-oss-120b"

mcp = FastMCP("openrouter_reasoner")

@mcp.tool()
async def reason_and_plan(prompt: str, tools: list):
    """
    Reason about the user prompt and decide which MCP tools to call.
    """

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are an agent that selects and calls tools."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "tools": tools
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            OR_URL,
            headers={
                "Authorization": f"Bearer {OR_KEY}",
                "Content-Type": "application/json"
            },
            json=payload
        )

    return r.json()

if __name__ == "__main__":
    mcp.run(transport="streamable-http", port=8090)
