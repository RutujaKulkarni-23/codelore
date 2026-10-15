"""
Offline unit tests for MCP filesystem toolset configuration.
Validates:
- Toolset is built with a pinned version string (not "latest" or "@latest")
- Allowed directory strictly equals target project root
- tool_filter contains only read tools and zero write/edit/move/create tools
- Subprocess environment contains no NVIDIA or PINECONE API keys
"""
import pytest
from pathlib import Path
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from code_helper.settings import load_settings
from code_helper.mcp_config import build_filesystem_toolset, SERVER_PACKAGE, READ_ONLY_TOOL_FILTER


def test_mcp_toolset_instantiation_and_pinned_version():
    settings = load_settings()
    toolset = build_filesystem_toolset(settings)
    assert isinstance(toolset, McpToolset)

    # Version check
    assert "@latest" not in SERVER_PACKAGE
    assert "latest" not in SERVER_PACKAGE
    assert "@modelcontextprotocol/server-filesystem@1.0.0" == SERVER_PACKAGE

    # Inspect connection_params
    conn = toolset.connection_params
    assert isinstance(conn, StdioConnectionParams)
    server_params = conn.server_params

    # Command and args
    assert "npx" in server_params.command.lower()
    assert "-y" in server_params.args
    assert SERVER_PACKAGE in server_params.args
    assert not any("latest" in arg.lower() for arg in server_params.args)


def test_mcp_allowed_directory_equals_target_root():
    settings = load_settings()
    toolset = build_filesystem_toolset(settings)
    server_params = toolset.connection_params.server_params

    expected_target = str(Path(settings.target_project_path).resolve())
    assert expected_target in server_params.args
    # Allowed dir argument is passed to npx
    assert server_params.args[-1] == expected_target


def test_mcp_tool_filter_read_only_and_no_write_tools():
    settings = load_settings()
    toolset = build_filesystem_toolset(settings)

    # Tool filter must be a list of strings
    tool_filter = toolset.tool_filter
    assert isinstance(tool_filter, list)
    assert len(tool_filter) > 0

    # Explicit read tools present
    expected_read_tools = [
        "read_text_file",
        "list_directory",
        "directory_tree",
        "search_files",
        "get_file_info",
    ]
    for tool_name in expected_read_tools:
        assert tool_name in tool_filter

    # Zero write / destructive tools reachable
    forbidden_verbs = ["write", "edit", "move", "create", "delete", "remove", "rename"]
    for tool_name in tool_filter:
        for verb in forbidden_verbs:
            assert verb not in tool_name.lower(), f"Forbidden tool '{tool_name}' exposed in tool_filter"


def test_mcp_subprocess_env_sanitized_no_keys():
    settings = load_settings()
    toolset = build_filesystem_toolset(settings)
    env = toolset.connection_params.server_params.env

    assert env is not None, "Explicit sanitized env dictionary must be provided"
    for key in env.keys():
        assert "nvidia" not in key.lower(), f"Leaked NVIDIA env var to MCP subprocess: {key}"
        assert "pinecone" not in key.lower(), f"Leaked PINECONE env var to MCP subprocess: {key}"

    # Only safe minimal keys
    allowed_keys = {"PATH", "SYSTEMROOT", "TEMP", "USERPROFILE"}
    for key in env.keys():
        assert key.upper() in allowed_keys, f"Unexpected env var passed to MCP subprocess: {key}"
