import asyncio
import httpx
import json

MCP_URL = "http://127.0.0.1:8080/mcp"


class FastMCPSSEClient:
    def __init__(self, url: str):
        self.url = url
        self.session_id = None
        self.client = httpx.AsyncClient(timeout=None)
        self.incoming = asyncio.Queue()

    async def start(self):
        # 1️⃣ Initialize MCP session
        print("🚀 Initializing MCP session")

        r = await self.client.post(
            self.url,
            headers={
                # MUST accept both for FastMCP
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "custom-sse-client",
                        "version": "1.0.0",
                    },
                },
            },
        )

        print(f"⬅️ Initialize status: {r.status_code}")
        r.raise_for_status()

        self.session_id = r.headers.get("mcp-session-id")
        if not self.session_id:
            raise RuntimeError("No mcp-session-id returned")

        print(f"✅ Session ID: {self.session_id}")

        # 2️⃣ Start SSE reader (server → client)
        asyncio.create_task(self._read_sse())

        # 3️⃣ REQUIRED MCP lifecycle notification
        await self.send({
            "jsonrpc": "2.0",
            "method": "initialized",
        })

    async def _read_sse(self):
        print("📡 Opening SSE stream")

        async with self.client.stream(
            "GET",
            self.url,
            headers={
                "Accept": "text/event-stream",
                "mcp-session-id": self.session_id,
            },
        ) as r:
            print(f"✅ SSE HTTP status: {r.status_code}")
            r.raise_for_status()

            print("🧵 SSE connected, waiting for events...")

            async for line in r.aiter_lines():
                if not line:
                    continue

                # Raw visibility (critical for debugging)
                print(f"📨 SSE RAW: {line}")

                if not line.startswith("data:"):
                    continue

                payload = line[5:].strip()
                try:
                    msg = json.loads(payload)
                    await self.incoming.put(msg)
                except json.JSONDecodeError:
                    print("⚠️ Non-JSON SSE payload ignored")

    async def send(self, message: dict):
        r = await self.client.post(
            self.url,
            headers={
                # STILL REQUIRED on POSTs after SSE is open
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
                "mcp-session-id": self.session_id,
            },
            json=message,
        )

        print(f"➡️ POST {message.get('method')} → {r.status_code}")
        r.raise_for_status()

    async def recv(self):
        return await self.incoming.get()


async def main():
    client = FastMCPSSEClient(MCP_URL)
    await client.start()

    print("➡️ Requesting tool list")

    await client.send({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
    })

    while True:
        msg = await client.recv()

        print(f"⬅️ MCP MESSAGE: {msg}")

        if msg.get("id") == 2:
            tools = msg["result"]["tools"]
            print("\n🛠️ Available Tools:")
            for tool in tools:
                print(f"  - {tool['name']}")
            break


if __name__ == "__main__":
    asyncio.run(main())
