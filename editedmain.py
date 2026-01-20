# editedmain.py
# Purpose: Agent Builder compatibility ONLY
# - No tool logic changes
# - No OAuth changes
# - No transport changes
# - No OpenRouter changes
# - Only relaxes MCP tool schemas during discovery

import argparse
import logging
import os
import socket
import sys
from importlib import import_module
from dotenv import load_dotenv

from auth.oauth_config import reload_oauth_config, is_stateless_mode
from core.log_formatter import EnhancedLogFormatter, configure_file_logging
from core.utils import check_credentials_directory_permissions
from core.server import server, set_transport_mode, configure_server_for_http
from core.tool_tier_loader import resolve_tools_from_tier
from core.tool_registry import (
    set_enabled_tools as set_enabled_tool_names,
    wrap_server_tool_method,
    filter_server_tools,
)

# ─────────────────────────────────────────────
# Environment & logging
# ─────────────────────────────────────────────

dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=dotenv_path)

logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)

reload_oauth_config()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

configure_file_logging()


def configure_safe_logging():
    class SafeEnhancedFormatter(EnhancedLogFormatter):
        def format(self, record):
            try:
                return super().format(record)
            except UnicodeEncodeError:
                prefix = self._get_ascii_prefix(record.name, record.levelname)
                msg = (
                    str(record.getMessage())
                    .encode("ascii", errors="replace")
                    .decode("ascii")
                )
                return f"{prefix} {msg}"

    for handler in logging.root.handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.setFormatter(SafeEnhancedFormatter(use_colors=True))


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    configure_safe_logging()

    parser = argparse.ArgumentParser("Google Workspace MCP Server")
    parser.add_argument("--single-user", action="store_true")
    parser.add_argument(
        "--tools",
        nargs="*",
        choices=[
            "gmail",
            "drive",
            "calendar",
            "docs",
            "sheets",
            "chat",
            "forms",
            "slides",
            "tasks",
            "search",
        ],
    )
    parser.add_argument("--tool-tier", choices=["core", "extended", "complete"])
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
    )
    args = parser.parse_args()

    port = int(os.getenv("PORT", os.getenv("WORKSPACE_MCP_PORT", 8000)))

    tool_imports = {
        "gmail": lambda: import_module("gmail.gmail_tools"),
        "calendar": lambda: import_module("gcalendar.calendar_tools"),
    }

    # ─────────────────────────────────────────────
    # Tool selection
    # ─────────────────────────────────────────────

    if args.tool_tier:
        tier_tools, suggested = resolve_tools_from_tier(args.tool_tier, args.tools)
        tools_to_import = args.tools or suggested
        set_enabled_tool_names(set(tier_tools))
    elif args.tools:
        tools_to_import = args.tools
        set_enabled_tool_names(None)
    else:
        tools_to_import = tool_imports.keys()
        set_enabled_tool_names(None)

    # Wrap + load tools
    wrap_server_tool_method(server)

    from auth.scopes import set_enabled_tools
    set_enabled_tools(list(tools_to_import))

    for tool in tools_to_import:
        tool_imports[tool]()

    filter_server_tools(server)

    # ─────────────────────────────────────────────
    # 🔑 AGENT BUILDER FIX
    # Relax tool schemas during discovery ONLY
    # ─────────────────────────────────────────────

    original_list_tools = server._list_tools

    def patched_list_tools():
        tools = original_list_tools()
        for tool in tools:
            schema = tool.get("inputSchema")
            if not schema:
                continue
            # Agent Builder rejects required fields
            schema.pop("required", None)
            # Ensure defaults are JSON-safe
            for prop in schema.get("properties", {}).values():
                if "default" in prop and prop["default"] is None:
                    continue
        return tools

    server._list_tools = patched_list_tools

    # ─────────────────────────────────────────────
    # Runtime mode
    # ─────────────────────────────────────────────

    if args.single_user:
        if is_stateless_mode():
            sys.exit(1)
        os.environ["MCP_SINGLE_USER_MODE"] = "1"

    if not is_stateless_mode():
        check_credentials_directory_permissions()

    set_transport_mode(args.transport)

    if args.transport == "streamable-http":
        configure_server_for_http()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", port))
        server.run(transport="streamable-http", host="0.0.0.0", port=port)
    else:
        server.run()


if __name__ == "__main__":
    main()
