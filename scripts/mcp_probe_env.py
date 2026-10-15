"""
Gap Probe: Filesystem MCP Server reading .env files.
Runs WITHOUT any language model.
Verifies whether @modelcontextprotocol/server-filesystem permits reading .env files
inside its configured root directory.
NEVER prints the file contents or secrets.
"""
import asyncio
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from code_helper.mcp_config import build_filesystem_toolset
from code_helper.settings import Settings
from google.adk.tools.tool_context import ToolContext


async def run_env_probe():
    temp_dir = Path(tempfile.mkdtemp(prefix="codelore_mcp_env_probe_"))
    try:
        # 1. Create sample.py
        sample_file = temp_dir / "sample.py"
        sample_file.write_text("print('sample probe')\n", encoding="utf-8")

        # 2. Create .env with runtime string-concatenated fake secret
        fake_key_part1 = "FAKE_SECRET_"
        fake_key_part2 = "TOKEN_9999"
        fake_key = fake_key_part1 + fake_key_part2
        env_file = temp_dir / ".env"
        env_file.write_text("TEST_API_KEY=" + fake_key + "\n", encoding="utf-8")

        print(f"Created temporary probe sandbox: {temp_dir}")
        print(f"Contains .env: {env_file.exists()}, size: {env_file.stat().st_size} bytes")

        from dataclasses import replace
        from code_helper.settings import load_settings
        dummy_settings = replace(load_settings(), target_project_path=temp_dir)

        toolset = build_filesystem_toolset(dummy_settings)
        mock_ctx = MagicMock(spec=ToolContext)
        mock_ctx.tool_confirmation = None
        mock_ctx.custom_metadata = {}

        tools = await toolset.get_tools()
        read_tool = next((t for t in tools if t.name == "read_text_file"), None)
        assert read_tool is not None, "read_text_file not found in toolset"

        print("\nAttempting read_text_file on .env through MCP server...")
        res = await read_tool.run_async(args={"path": str(env_file)}, tool_context=mock_ctx)

        # Inspect success and length WITHOUT ever printing content
        call_succeeded = False
        content_len = 0

        if isinstance(res, dict) and "content" in res:
            text_blocks = [item.get("text", "") for item in res["content"] if isinstance(item, dict)]
            combined = "".join(text_blocks)
            call_succeeded = True
            content_len = len(combined)
        elif isinstance(res, str) and not res.startswith("Error"):
            call_succeeded = True
            content_len = len(res)

        print("\n--- MCP .env Probe Results ---")
        print(f"Call Succeeded: {call_succeeded}")
        print(f"Content Length > 0: {content_len > 0}")
        print(f"Byte Count Read: {content_len} bytes")
        print("Note: Secret contents are never printed or logged.")

        return call_succeeded, content_len > 0

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        print("Temporary sandbox cleaned up.")


if __name__ == "__main__":
    asyncio.run(run_env_probe())
