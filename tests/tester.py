import httpx
import json

MCP_URL = "http://127.0.0.1:8080/mcp"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

USER_EMAIL = "prasannah@aiatcore.com"   # <-- MUST MATCH YOUR AUTH USER
MESSAGE_IDS = ["19bb2636ca81bb77"]    # from tools/list result


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
                        "name": "gmail-content-client",
                        "version": "1.0.0",
                    },
                },
            },
        )

        init_resp.raise_for_status()
        session_id = init_resp.headers["mcp-session-id"]
        print("✅ Session ID:", session_id)

        # 2️⃣ Send initialized notification
        client.post(
            MCP_URL,
            headers={**HEADERS, "mcp-session-id": session_id},
            json={
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            },
        )

        # 3️⃣ Call get_gmail_messages_content_batch
        print("➡️ Fetching full message content")
        print("⏳ Waiting for message data...")

        with client.stream(
            "POST",
            MCP_URL,
            headers={**HEADERS, "mcp-session-id": session_id},
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "get_gmail_messages_content_batch",
                    "arguments": {
                        "user_google_email": USER_EMAIL,
                        "message_ids": MESSAGE_IDS,
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

                    print("📥 MESSAGE CONTENT:")
                    print(json.dumps(msg, indent=2))

                    break


if __name__ == "__main__":
    main()
