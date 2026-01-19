import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client

async def main():
    # 1. Connect to the SSE endpoint
    # The SDK handles the discovery of the /messages endpoint for you.
    async with sse_client("http://localhost:8080/sse") as (read_stream, write_stream):
        
        # 2. Initialize the session
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            print("✅ Connected to Google Workspace MCP!")

            # 3. List and use tools
            tools = await session.list_tools()
            print(f"\n🛠️ Found {len(tools.tools)} tools:")
            for tool in tools.tools:
                print(f"  - {tool.name}: {tool.description[:50]}...")

            # Example: Call a tool (optional)
            # result = await session.call_tool("search_gmail_messages", {"query": "from:me"})
            # print(result)

if __name__ == "__main__":
    asyncio.run(main())