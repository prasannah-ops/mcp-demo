import httpx
import json

MCP_URL = "http://127.0.0.1:8080/mcp"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

def main():
    with httpx.Client(timeout=None) as client:

        # 1️⃣ Initialize
        print("🚀 Initializing MCP session")

        init_resp = client.post(
            MCP_URL,
            headers=HEADERS,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-10-07",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "tool-call-client",
                        "version": "1.0.0",
                    },
                },
            },
        )

        print("⬅️ Initialize status:", init_resp.status_code)
        init_resp.raise_for_status()

        session_id = init_resp.headers["mcp-session-id"]
        print("✅ Session ID:", session_id)

        # 2️⃣ Send initialized notification
        print("➡️ Sending notifications/initialized")

        client.post(
            MCP_URL,
            headers={**HEADERS, "mcp-session-id": session_id},
            json={
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            },
        )

        # 3️⃣ Call a tool (STREAMING RESPONSE)
        print("➡️ Calling tool: search_gmail_messages")
        print("⏳ Waiting for tool response...")

        with client.stream(
            "POST",
            MCP_URL,
            headers={**HEADERS, "mcp-session-id": session_id},
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "search_gmail_messages",   
                    "arguments": {
                        "user_google_email": "prasannah@aiatcore.com",
                        "query": "from:me"
                    },
                },
            },
        ) as resp:

            resp.raise_for_status()

            for line in resp.iter_lines():
                if not line:
                    continue

                if line.startswith("data:"):
                    payload = line.removeprefix("data:").strip()
                    msg = json.loads(payload)

                    print("📥 TOOL RESPONSE:")
                    print(json.dumps(msg, indent=2))

                    # tools/call returns exactly one response
                    break


if __name__ == "__main__":
    main()
