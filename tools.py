def list_tools():
    return [
        {
            "name": "echo",
            "description": "Echoes input text",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"}
                },
                "required": ["text"]
            }
        }
    ]


def call_tool(name: str, arguments: dict):
    if name == "echo":
        return {
            "content": [
                {
                    "type": "text",
                    "text": arguments["text"]
                }
            ]
        }

    raise ValueError(f"Unknown tool: {name}")
