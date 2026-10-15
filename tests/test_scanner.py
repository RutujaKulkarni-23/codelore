import os
import pytest
from pathlib import Path
from code_helper.rag.scanner import scan_python_files, scan_metadata_files, ScanResult


def test_scan_python_files_basic(tmp_path):
    # Setup test structure
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text("print('hello')\n", encoding="utf-8")
    (src / "util.py").write_text("x = 1\n", encoding="utf-8")

    sub = src / "subpkg"
    sub.mkdir()
    (sub / "helper.py").write_text("def run(): pass\n", encoding="utf-8")

    res = scan_python_files(tmp_path)
    assert isinstance(res, ScanResult)
    # Must use forward slashes
    assert "src/app.py" in res.files
    assert "src/util.py" in res.files
    assert "src/subpkg/helper.py" in res.files
    assert not res.truncated


def test_scan_python_files_excludes_ignored_directories(tmp_path):
    # Create ignored folders
    for d in [".git", ".venv", "venv", "__pycache__", "node_modules", ".hidden"]:
        p = tmp_path / d
        p.mkdir()
        (p / "bad.py").write_text("should_be_skipped = True\n", encoding="utf-8")

    (tmp_path / "good.py").write_text("valid = True\n", encoding="utf-8")

    res = scan_python_files(tmp_path)
    assert res.files == ["good.py"]


def test_scan_caps_and_oversized_files(tmp_path):
    # Create file larger than max_file_bytes
    (tmp_path / "small.py").write_text("a = 1\n", encoding="utf-8")
    huge_file = tmp_path / "huge.py"
    huge_file.write_text("x" * 500, encoding="utf-8")

    res = scan_python_files(tmp_path, max_files=10, max_file_bytes=200)
    assert "small.py" in res.files
    assert "huge.py" not in res.files
    assert any(s[0] == "huge.py" and "file_size_exceeded" in s[1] for s in res.skipped)


def test_scan_truncation_cap(tmp_path):
    for i in range(5):
        (tmp_path / f"file_{i}.py").write_text(f"v = {i}\n", encoding="utf-8")

    res = scan_python_files(tmp_path, max_files=3)
    assert len(res.files) == 3
    assert res.truncated is True


def test_scan_utf8_decode_error(tmp_path):
    bad_file = tmp_path / "corrupt.py"
    # Write invalid non-UTF-8 bytes
    bad_file.write_bytes(b"\xff\xfe\x00\x00 invalid utf8")

    res = scan_python_files(tmp_path)
    assert "corrupt.py" not in res.files
    assert any(s[0] == "corrupt.py" and "utf8_decode_error" in s[1] for s in res.skipped)


def test_scan_metadata_files(tmp_path):
    (tmp_path / "README.md").write_text("# Readme\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    (tmp_path / "ignore.py").write_text("pass\n", encoding="utf-8")

    meta = scan_metadata_files(tmp_path)
    assert "README.md" in meta
    assert "requirements.txt" in meta
    assert "pyproject.toml" in meta
    assert "ignore.py" not in meta


def test_scan_symlink_escape(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.py").write_text("secret = 42\n", encoding="utf-8")

    inside = tmp_path / "inside"
    inside.mkdir()
    link = inside / "link_to_outside.py"

    try:
        os.symlink(outside / "secret.py", link)
    except (OSError, NotImplementedError) as e:
        pytest.skip(f"Windows symlink creation privileges not granted: {e}")

    res = scan_python_files(inside)
    # Symlinks should never be included
    assert "link_to_outside.py" not in res.files
    assert any("symlink" in s[1] for s in res.skipped)
