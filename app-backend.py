# backend.py
from fastapi import FastAPI, Request
import httpx

AGENT_BUILDER_URL = "https://your-agent-builder-endpoint"

app = FastAPI()

@app.post("/api/chat")
async def chat(request: Request):
    payload = await request.json()

    async with httpx.AsyncClient(timeout=None) as client:
        resp = await client.post(
            AGENT_BUILDER_URL,
            json={
                "input": payload["message"]
            },
            stream=True
        )

        return resp.json()  # or stream back if supported
