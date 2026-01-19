import httpx
import os
import json
from dotenv import load_dotenv

load_dotenv(override=True)

# 1. Configuration
KEY = os.getenv("OPENROUTER_API_KEY")
URL_CHECK = "https://openrouter.ai/api/v1/auth/key"

HEADERS = {
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "http://localhost:8081",
    "X-Title": "Key-Test-Script"
}

async def check_billing():
    async with httpx.AsyncClient(timeout=30.0) as client:
        print(f"📡 Checking Key with OpenRouter: {KEY[:10]}...")

        try:
            response = await client.get(URL_CHECK, headers=HEADERS)
            
            if response.status_code == 200:
                data = response.json()
                print("\n✅ CONNECTION SUCCESSFUL!")
                print("-----------------------------------------")
                print(f"Key Label: {data.get('data', {}).get('label')}")
                
                # Check the math
                limit = data.get('data', {}).get('limit')
                usage = data.get('data', {}).get('usage', 0)
                
                if limit is None:
                    print("Usage: Uncapped (Unlimited)")
                else:
                    balance = limit - usage
                    print(f"Usage: ${usage:.4f}")
                    print(f"Limit: ${limit:.4f}")
                    print(f"REMAINING BALANCE: ${balance:.4f}")
                    
                    if balance <= 0:
                        print("\n🚨 ERROR: THIS KEY HAS $0.00 REMAINING.")
                print("-----------------------------------------")
            else:
                print(f"\n❌ SERVER REJECTED THE KEY (Status {response.status_code})")
                print(f"Error Message: {response.text}")

        except Exception as e:
            print(f"\n❌ NETWORK ERROR: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(check_billing())