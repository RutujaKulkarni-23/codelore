import ast
from pathlib import Path
from typing import Any

from code_helper.tools._context import get_project_root
from code_helper.tools._paths import safe_resolve, cap_output, wrap_untrusted_code, PathSecurityError


def get_file_outline(path: str) -> str:
    """
    Extract an outline of a Python source file including docstrings, imports, classes, methods, and functions.
    Use this tool when you need a clear overview of the structure and exact line ranges of a specific file.
    """
    if not isinstance(path, str) or not path.strip():
        return "ERROR: path parameter cannot be empty or blank."
    if len(path) > 200:
        return f"ERROR: path parameter length ({len(path)}) exceeds maximum limit of 200 characters."

    root = get_project_root()
    try:
        resolved_path = safe_resolve(root, path)
    except PathSecurityError as e:
        return f"ERROR: Path security validation failed: {e}"
    except Exception as e:
        return f"ERROR: Invalid path: {e}"

    if not resolved_path.exists():
        return f"ERROR: File '{path}' does not exist under project root."
    if resolved_path.is_dir():
        return f"ERROR: Path '{path}' is a directory, not a Python file."
    if resolved_path.suffix != ".py":
        return f"ERROR: Only Python (.py) files can be outlined, got '{resolved_path.name}'."

    try:
        content = resolved_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = resolved_path.read_bytes().decode("utf-8", errors="replace")

    try:
        tree = ast.parse(content, filename=path)
    except SyntaxError as e:
        return f"ERROR: Failed to parse Python syntax in '{path}': {e}"

    lines = [f"Outline for {path} (total lines: {len(content.splitlines())}):\n"]

    # Module docstring
    module_doc = ast.get_docstring(tree)
    if module_doc:
        first_doc_line = module_doc.strip().splitlines()[0]
        lines.append(f"Module Docstring: \"{first_doc_line}\"\n")
    else:
        lines.append("Module Docstring: <none>\n")

    # Imports
    import_entries: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            mod_names = ", ".join(alias.name for alias in node.names)
            import_entries.append(f"  - L{node.lineno}: import {mod_names}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            names = ", ".join(alias.name for alias in node.names)
            dots = "." * node.level
            import_entries.append(f"  - L{node.lineno}: from {dots}{mod} import {names}")

    if import_entries:
        lines.append(f"Imports ({len(import_entries)}):")
        lines.extend(import_entries)
        lines.append("")

    # Classes and top-level functions
    definitions: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            c_doc = ast.get_docstring(node)
            c_doc_first = f" - \"{c_doc.strip().splitlines()[0]}\"" if c_doc else ""
            c_end = getattr(node, "end_lineno", node.lineno)
            definitions.append(f"Class: {node.name} -> {path}:{node.lineno}-{c_end}{c_doc_first}")

            # Methods
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    m_doc = ast.get_docstring(item)
                    m_doc_first = f" - \"{m_doc.strip().splitlines()[0]}\"" if m_doc else ""
                    m_end = getattr(item, "end_lineno", item.lineno)
                    kind_str = "async def" if isinstance(item, ast.AsyncFunctionDef) else "def"
                    definitions.append(f"    • {kind_str} {item.name}() -> {path}:{item.lineno}-{m_end}{m_doc_first}")

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            f_doc = ast.get_docstring(node)
            f_doc_first = f" - \"{f_doc.strip().splitlines()[0]}\"" if f_doc else ""
            f_end = getattr(node, "end_lineno", node.lineno)
            kind_str = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            definitions.append(f"Function: {kind_str} {node.name}() -> {path}:{node.lineno}-{f_end}{f_doc_first}")

    if definitions:
        lines.append(f"Definitions ({len(definitions)}):")
        lines.extend(definitions)
    else:
        lines.append("Definitions: <no classes or functions defined>")

    return cap_output("\n".join(lines))
