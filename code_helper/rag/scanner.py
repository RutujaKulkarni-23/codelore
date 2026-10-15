import os
import re
from dataclasses import dataclass, field
from pathlib import Path


EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "node_modules",
    "build",
    "dist",
    "site-packages",
    ".mypy_cache",
    ".pytest_cache",
}

WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


@dataclass
class ScanResult:
    files: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    truncated: bool = False


def _is_safe_relative_path(rel_str: str) -> bool:
    """Validate relative path to prevent traversal, reserved names, or drive letters."""
    if not rel_str or rel_str.strip() == "":
        return False
    # Reject absolute, drive letters, or parent directory traversal
    if os.path.isabs(rel_str) or ":" in rel_str or "\\" in rel_str:
        return False
    parts = rel_str.split("/")
    for p in parts:
        if p == ".." or p == ".":
            return False
        # Windows reserved devices check
        stem = p.split(".")[0].upper()
        if stem in WINDOWS_RESERVED_NAMES:
            return False
    return True


def scan_python_files(
    root: Path,
    max_files: int = 2000,
    max_file_bytes: int = 200000,
) -> ScanResult:
    """
    Scans a directory recursively for Python files (.py).
    Enforces path safety, directory exclusions, symlink protection, and size caps.
    Returns relative POSIX-style paths.
    """
    root_resolved = root.resolve()
    if not root_resolved.exists() or not root_resolved.is_dir():
        raise ValueError(f"Root path does not exist or is not a directory: {root}")

    result = ScanResult()
    py_files_found: list[Path] = []

    for dirpath, dirnames, filenames in os.walk(root_resolved, followlinks=False):
        current_dir = Path(dirpath)

        # Check symlink on directory itself
        if current_dir.is_symlink():
            dirnames.clear()
            continue

        # Filter out excluded or hidden directories in-place
        dirnames[:] = [
            d for d in dirnames
            if d not in EXCLUDED_DIRS
            and not d.startswith(".")
            and not (current_dir / d).is_symlink()
        ]

        for fname in sorted(filenames):
            if not fname.endswith(".py"):
                continue

            file_path = current_dir / fname

            # Reject symlinks
            if file_path.is_symlink():
                try:
                    rel_sym = file_path.relative_to(root_resolved).as_posix()
                except ValueError:
                    rel_sym = fname
                result.skipped.append((rel_sym, "symlink_ignored"))
                continue

            # Ensure file is strictly inside root
            try:
                resolved_file = file_path.resolve()
                if not resolved_file.is_relative_to(root_resolved):
                    rel = file_path.name
                    result.skipped.append((rel, "path_traversal_escape"))
                    continue
            except Exception as e:
                result.skipped.append((fname, f"resolve_error: {e}"))
                continue

            rel_posix = file_path.relative_to(root_resolved).as_posix()
            if not _is_safe_relative_path(rel_posix):
                result.skipped.append((rel_posix, "unsafe_path_characters"))
                continue

            # Check file byte size
            try:
                size = file_path.stat().st_size
                if size > max_file_bytes:
                    result.skipped.append((rel_posix, f"file_size_exceeded ({size} > {max_file_bytes} bytes)"))
                    continue
            except Exception as e:
                result.skipped.append((rel_posix, f"stat_error: {e}"))
                continue

            # Check UTF-8 readability without crashing
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    f.read()
            except UnicodeDecodeError:
                result.skipped.append((rel_posix, "utf8_decode_error"))
                continue
            except Exception as e:
                result.skipped.append((rel_posix, f"read_error: {e}"))
                continue

            py_files_found.append(file_path)
            if len(py_files_found) >= max_files:
                result.truncated = True
                break

        if result.truncated:
            break

    # Sort files deterministically by POSIX path
    result.files = sorted([p.relative_to(root_resolved).as_posix() for p in py_files_found])
    return result


def scan_metadata_files(root: Path) -> list[str]:
    """
    Finds project metadata files (README*, requirements*.txt, pyproject.toml, setup.cfg).
    These are referenced for project onboarding but are not chunked or embedded.
    """
    root_resolved = root.resolve()
    if not root_resolved.exists() or not root_resolved.is_dir():
        return []

    metadata_files: list[str] = []
    # Check top-level and first subdirectory level
    patterns = [
        "README*",
        "requirements*.txt",
        "pyproject.toml",
        "setup.cfg",
    ]

    for pat in patterns:
        for p in root_resolved.glob(pat):
            if p.is_file() and not p.is_symlink():
                rel = p.relative_to(root_resolved).as_posix()
                if rel not in metadata_files:
                    metadata_files.append(rel)

    return sorted(metadata_files)
