import asyncio
import sys
import os
from types import SimpleNamespace

from mcp import ClientSession
from mcp.client.stdio import stdio_client


SERVER = SimpleNamespace(
    command=sys.executable,
    args=[
        "main.py",
        "--transport",
        "stdio",
    ],
    env=None,
    cwd=os.getcwd(),   # 🔑 REQUIRED
)


async def main():
    print("🚀 Starting FastMCP stdio server")

    async with stdio_client(SERVER) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            print("✅ Connected to MCP server")

            # REQUIRED MCP lifecycle step
            await session.send_notification("initialized")

            print("➡️ Listing tools")
            tools = await session.list_tools()

            print("\n🛠️ Available Tools:")
            for tool in tools.tools:
                print(f"  - {tool.name}")


if __name__ == "__main__":
    asyncio.run(main())
