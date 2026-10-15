"""
Pytest wrapper for scripts/tool_smoke_test.py.
Skips if the target folder is missing.
"""
import os
import sys
from pathlib import Path

import pytest

TARGET_DIR = Path("D:/CodeLore/targets/Naive_RAG")

@pytest.mark.skipif(
    not TARGET_DIR.exists(),
    reason="Target folder D:/CodeLore/targets/Naive_RAG not found"
)
def test_tool_smoke():
    """Run the full offline tool smoke test against the real target."""
    # Ensure codelore root is importable
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # Point tools at real target
    os.environ["CODELORE_PROJECT_ROOT"] = str(TARGET_DIR)

    # Import and run
    from scripts.tool_smoke_test import run_smoke_tests
    exit_code = run_smoke_tests()
    assert exit_code == 0, "Tool smoke test reported failures"
