import pytest
from pathlib import Path
from code_helper.rag.chunker import (
    chunk_file_ast_hybrid,
    chunk_file_fixed_window,
    chunk_source_file,
    Chunk,
)


def _reconstruct_body(chunk_text: str) -> str:
    """Strips the first header line to retrieve raw chunk body."""
    lines = chunk_text.splitlines(keepends=True)
    if lines and lines[0].startswith("# file:"):
        return "".join(lines[1:])
    return chunk_text


def test_chunk_lines_match_source():
    source = (
        "import os\n"
        "\n"
        "def add(x, y):\n"
        "    return x + y\n"
        "\n"
        "class Greeter:\n"
        "    def greet(self):\n"
        "        return 'hello'\n"
    )
    source_lines = source.splitlines(keepends=True)
    chunks = chunk_file_ast_hybrid(source, "dummy.py", max_chunk_lines=50)

    assert len(chunks) > 0
    for c in chunks:
        expected = "".join(source_lines[c.start_line - 1: c.end_line])
        actual = _reconstruct_body(c.text)
        assert actual == expected


def test_small_function_stays_whole():
    source = (
        "def small_func(a, b):\n"
        "    '''A small helper.'''\n"
        "    result = a * b\n"
        "    return result\n"
    )
    chunks = chunk_file_ast_hybrid(source, "math_util.py", max_chunk_lines=60)
    func_chunks = [c for c in chunks if c.kind == "function"]
    assert len(func_chunks) == 1
    assert func_chunks[0].symbol == "small_func"
    assert func_chunks[0].start_line == 1
    assert func_chunks[0].end_line == 4


def test_huge_function_splits_with_overlap():
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "sample_project" / "pkg" / "huge_func.py"
    source = fixture_path.read_text(encoding="utf-8")
    chunks = chunk_file_ast_hybrid(source, "huge_func.py", max_chunk_lines=40, chunk_overlap_lines=8)

    # Function is ~260 lines, should be split into multiple chunks
    assert len(chunks) > 1
    for i in range(len(chunks) - 1):
        # Verify overlap between consecutive chunks
        assert chunks[i].end_line > chunks[i + 1].start_line


def test_syntax_error_fallback_to_windows():
    broken_code = (
        "def invalid_python(\n"
        "    missing_close_paren = 123\n"
        "    for item in [\n"
    )
    chunks = chunk_file_ast_hybrid(broken_code, "broken.py", max_chunk_lines=10)
    assert len(chunks) >= 1
    assert all(c.kind == "window" for c in chunks)
    assert all(c.symbol == "<syntax_error_fallback>" for c in chunks)


def test_deterministic_chunk_ids():
    source = "def func_a(): pass\ndef func_b(): pass\n"
    run_1 = chunk_file_ast_hybrid(source, "mod.py")
    run_2 = chunk_file_ast_hybrid(source, "mod.py")

    assert [c.id for c in run_1] == [c.id for c in run_2]
    assert [c.content_hash for c in run_1] == [c.content_hash for c in run_2]


def test_fixed_window_chunker():
    source = "def foo():\n    return 42\n" * 20
    chunks = chunk_file_fixed_window(source, "long.py", window_chars=100, overlap_chars=20)
    assert len(chunks) > 1
    assert all(c.kind == "window" for c in chunks)
    assert all(c.symbol == "<window>" for c in chunks)
