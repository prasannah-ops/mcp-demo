import asyncio
import httpx
from mcp.client.sse import sse_client

async def diagnose():
    # We will test the three most likely endpoints for this specific server
    endpoints = [
        "http://localhost:8080/mcp"
    ]
    
    for url in endpoints:
        print(f"\n🔍 Testing: {url}")
        try:
            # We use a standard httpx request first to see what the server says
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=2.0)
                print(f"   Result: HTTP {response.status_code}")
                if response.status_code == 200:
                    print(f"   ✅ SUCCESS! This is the correct URL.")
                    return url
                else:
                    print(f"   ❌ Failed: {response.text[:50]}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(diagnose())