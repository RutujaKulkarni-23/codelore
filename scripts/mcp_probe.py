"""
Probe script for Filesystem MCP server integration.
Runs WITHOUT any language model.
Verifies:
1. Toolset starts using build_filesystem_toolset(settings)
2. Lists exposed tools (names only) - verifies zero write tools
3. Reads a real file from the target project (prints line count only)
4. Tries reading outside target via relative path ("../../codelore/requirements.txt")
5. Tries reading outside target via absolute path
6. Verifies write tool is absent / uncallable
"""
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from code_helper.settings import load_settings
from code_helper.mcp_config import build_filesystem_toolset
from google.adk.tools.tool_context import ToolContext


async def run_probe():
    settings = load_settings()
    target_dir = Path(settings.target_project_path).resolve()
    print(f"Target project path: {target_dir}")
    print(f"Target exists: {target_dir.exists()}")

    print("")
    print("--- 1. Starting Filesystem MCP Server through build_filesystem_toolset ---")
    toolset = build_filesystem_toolset(settings)

    mock_ctx = MagicMock(spec=ToolContext)
    mock_ctx.tool_confirmation = None
    mock_ctx.custom_metadata = {}

    try:
        # Retrieve tools via ADK McpToolset
        tools = await toolset.get_tools()
        tool_names = [t.name for t in tools]
        print("")
        print("--- 2. Exposed Tools (names only) ---")
        for name in sorted(tool_names):
            print(f"  - {name}")

        # Check for write tools
        write_names = [name for name in tool_names if any(w in name.lower() for w in ["write", "edit", "move", "create", "delete", "rename"])]
        print(f"Write tools present in toolset: {write_names} (Expected: [])")
        assert len(write_names) == 0, f"Dangerous write tools found: {write_names}"

        # Find read_text_file tool
        read_tool = next((t for t in tools if t.name == "read_text_file"), None)
        assert read_tool is not None, "read_text_file tool not found in toolset"

        print("")
        print("--- 3. Read Real File in Target (print line count only) ---")
        target_file = target_dir / "indexer.py"
        if not target_file.exists():
            target_file = next(target_dir.glob("*.py"))
        print(f"Reading target file: {target_file.name}")
        res_real = await read_tool.run_async(args={"path": str(target_file)}, tool_context=mock_ctx)
        # Extract text payload
        if isinstance(res_real, dict) and "content" in res_real:
            text_blocks = [item.get("text", "") for item in res_real["content"] if isinstance(item, dict)]
            actual_text = chr(10).join(text_blocks)
            line_count = len(actual_text.splitlines())
        else:
            line_count = len(str(res_real).splitlines())
        print(f"Result: Success! Content line count: {line_count}")

        print("")
        print("--- 4. Attempt Reading Outside via Relative Traversal ('../../codelore/requirements.txt') ---")
        try:
            res_rel = await read_tool.run_async(args={"path": "../../codelore/requirements.txt"}, tool_context=mock_ctx)
            res_str = str(res_rel)
            if "error" in res_str.lower() or "denied" in res_str.lower() or "outside" in res_str.lower():
                print(f"Result: Rejected as expected! Message: {res_str[:120]}...")
            else:
                print(f"WARNING: Unexpected response: {res_str[:120]}")
        except Exception as e:
            print(f"Result: Rejected with exception as expected: {type(e).__name__}: {e}")

        print("")
        print("--- 5. Attempt Reading Outside via Absolute Path ---")
        outside_path = str(PROJECT_ROOT / "requirements.txt")
        print(f"Attempting path: {outside_path}")
        try:
            res_abs = await read_tool.run_async(args={"path": outside_path}, tool_context=mock_ctx)
            res_str = str(res_abs)
            if "error" in res_str.lower() or "denied" in res_str.lower() or "outside" in res_str.lower():
                print(f"Result: Rejected as expected! Message: {res_str[:120]}...")
            else:
                print(f"WARNING: Unexpected response: {res_str[:120]}")
        except Exception as e:
            print(f"Result: Rejected with exception as expected: {type(e).__name__}: {e}")

        print("")
        print("--- 6. Attempt Calling a Write Tool Name ('write_file') ---")
        write_tool = next((t for t in tools if t.name == "write_file"), None)
        if write_tool is None:
            print("Result: Verified! 'write_file' does NOT exist in the exposed toolset and cannot be called.")
        else:
            print("ERROR: 'write_file' unexpectedly exists in toolset!")

    finally:
        await toolset.close()
        print("")
        print("Toolset closed cleanly.")


if __name__ == "__main__":
    asyncio.run(run_probe())
