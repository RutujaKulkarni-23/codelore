"""
MCP Filesystem Toolset Configuration for Code Explainer.
Configures read-only access to the target project via @modelcontextprotocol/server-filesystem.
"""
import os
import shutil
from pathlib import Path
from mcp import StdioServerParameters
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from code_helper.settings import Settings

SERVER_PACKAGE = "@modelcontextprotocol/server-filesystem@1.0.0"

READ_ONLY_TOOL_FILTER = [
    "read_text_file",
    "list_directory",
    "directory_tree",
    "search_files",
    "get_file_info",
]


def build_filesystem_toolset(settings: Settings) -> McpToolset:
    """
    Build an McpToolset connecting to a read-only filesystem MCP server.
    Restricts allowed directory to settings.target_project_path only.
    Sanitizes environment variables to prevent leaking API keys.
    Filters tools to read-only operations.
    """
    target_path = str(Path(settings.target_project_path).resolve())
    npx_cmd = shutil.which("npx") or "npx.cmd"

    # Explicit minimal environment to prevent leaking API keys
    sanitized_env = {
        "PATH": os.environ.get("PATH", ""),
        "SystemRoot": os.environ.get("SystemRoot", ""),
        "TEMP": os.environ.get("TEMP", ""),
        "USERPROFILE": os.environ.get("USERPROFILE", ""),
    }

    server_params = StdioServerParameters(
        command=npx_cmd,
        args=["-y", SERVER_PACKAGE, target_path],
        env=sanitized_env,
    )

    connection_params = StdioConnectionParams(
        server_params=server_params,
        timeout=30.0,
    )

    return McpToolset(
        connection_params=connection_params,
        tool_filter=READ_ONLY_TOOL_FILTER,
    )
