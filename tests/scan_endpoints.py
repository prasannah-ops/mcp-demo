import httpx

async def scan():
    base_url = "http://localhost:3001"
    # These are the 4 most common paths for FastMCP servers
    paths = ["/", "/sse", "/mcp/sse", "/api/sse"]
    
    print(f"Checking server at {base_url}...")
    async with httpx.AsyncClient() as client:
        for path in paths:
            try:
                url = f"{base_url}{path}"
                response = await client.get(url)
                print(f"Path {path:10} : Status {response.status_code}")
            except Exception as e:
                print(f"Path {path:10} : Error {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(scan())