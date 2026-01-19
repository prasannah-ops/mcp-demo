import httpx
import json
import asyncio

# --- PASTE THE KEY FROM YOUR SUPERVISOR DIRECTLY HERE ---
# DO NOT USE os.getenv. DELETE THE OLD STRING AND PASTE THE NEW ONE.
TEST_KEY = "sk-or-v1-PASTE_SUPERVISOR_KEY_HERE"

async def test():
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {TEST_KEY}",
        "Content-Type": "application/json",
        "X-Title": "HARDCODED_AUTH_TEST"
    }
    payload = {
        "model": "meta-llama/llama-3.1-8b-instruct:free",
        "messages": [{"role": "user", "content": "Confirming key identity."}]
    }

    async with httpx.AsyncClient() as client:
        print(f"📡 Sending request with key starting with: {TEST_KEY[:12]}")
        response = await client.post(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            print("✅ Success!")
            print("Check the OpenRouter Activity Dashboard now.")
            print("Look for a request titled: 'HARDCODED_AUTH_TEST'")
        else:
            print(f"❌ Error {response.status_code}")
            print(response.text)

if __name__ == "__main__":
    asyncio.run(test())