import ast
from pathlib import Path
from typing import Any

from code_helper.tools._context import get_project_root
from code_helper.tools._paths import safe_resolve, cap_output, wrap_untrusted_code, PathSecurityError


def _parse_and_outline_file(path: str) -> tuple[str, int, str, list[str], list[str], list[str], dict[str, str]] | str:
    """Safely resolves and parses a Python target file, returning AST outline components."""
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

    total_lines = len(content.splitlines())

    # Module docstring
    module_doc = ast.get_docstring(tree)
    first_doc_line = module_doc.strip().splitlines()[0] if module_doc else "<none>"

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

    # Classes, methods, and top-level functions
    definitions: list[str] = []
    copy_ready_lines: list[str] = []
    symbol_ranges: dict[str, str] = {}
    struct_items: list[dict[str, Any]] = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            c_doc = ast.get_docstring(node)
            c_doc_first = f" - \"{c_doc.strip().splitlines()[0]}\"" if c_doc else ""
            c_start = node.decorator_list[0].lineno if node.decorator_list else node.lineno
            c_end = getattr(node, "end_lineno", node.lineno)
            definitions.append(f"Class: {node.name} -> {path}:{c_start}-{c_end}{c_doc_first}")

            bases_str = ", ".join(ast.unparse(b) for b in node.bases)
            copy_ready_lines.append(f"{node.name}({bases_str}) - {path}:{c_start}-{c_end}")
            c_first_doc = ""
            if c_doc:
                c_first_doc = next((line.strip() for line in c_doc.splitlines() if line.strip()), "")
                if c_first_doc:
                    copy_ready_lines.append(f"    {c_first_doc[:120]}")
            symbol_ranges[node.name] = f"{path}:{c_start}-{c_end}"
            struct_items.append({
                "name": node.name,
                "signature": f"({bases_str})" if bases_str else "()",
                "start": c_start,
                "end": c_end,
                "doc": c_first_doc[:120],
            })

            # Methods
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    m_doc = ast.get_docstring(item)
                    m_doc_first = f" - \"{m_doc.strip().splitlines()[0]}\"" if m_doc else ""
                    m_start = item.decorator_list[0].lineno if item.decorator_list else item.lineno
                    m_end = getattr(item, "end_lineno", item.lineno)
                    kind_str = "async def" if isinstance(item, ast.AsyncFunctionDef) else "def"
                    definitions.append(f"    • {kind_str} {item.name}() -> {path}:{m_start}-{m_end}{m_doc_first}")

                    m_params = ast.unparse(item.args)
                    m_ret = f" -> {ast.unparse(item.returns)}" if getattr(item, "returns", None) else ""
                    copy_ready_lines.append(f"{node.name}.{item.name}({m_params}) - {path}:{m_start}-{m_end}")
                    m_first_doc = ""
                    if m_doc:
                        m_first_doc = next((line.strip() for line in m_doc.splitlines() if line.strip()), "")
                        if m_first_doc:
                            copy_ready_lines.append(f"    {m_first_doc[:120]}")
                    symbol_ranges[f"{node.name}.{item.name}"] = f"{path}:{m_start}-{m_end}"
                    symbol_ranges[item.name] = f"{path}:{m_start}-{m_end}"
                    struct_items.append({
                        "name": f"{node.name}.{item.name}",
                        "signature": f"({m_params}){m_ret}",
                        "start": m_start,
                        "end": m_end,
                        "doc": m_first_doc[:120],
                    })

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            f_doc = ast.get_docstring(node)
            f_doc_first = f" - \"{f_doc.strip().splitlines()[0]}\"" if f_doc else ""
            f_start = node.decorator_list[0].lineno if node.decorator_list else node.lineno
            f_end = getattr(node, "end_lineno", node.lineno)
            kind_str = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            definitions.append(f"Function: {kind_str} {node.name}() -> {path}:{f_start}-{f_end}{f_doc_first}")

            f_params = ast.unparse(node.args)
            f_ret = f" -> {ast.unparse(node.returns)}" if getattr(node, "returns", None) else ""
            copy_ready_lines.append(f"{node.name}({f_params}) - {path}:{f_start}-{f_end}")
            f_first_doc = ""
            if f_doc:
                f_first_doc = next((line.strip() for line in f_doc.splitlines() if line.strip()), "")
                if f_first_doc:
                    copy_ready_lines.append(f"    {f_first_doc[:120]}")
            symbol_ranges[node.name] = f"{path}:{f_start}-{f_end}"
            struct_items.append({
                "name": node.name,
                "signature": f"({f_params}){f_ret}",
                "start": f_start,
                "end": f_end,
                "doc": f_first_doc[:120],
            })

    return path, total_lines, first_doc_line, import_entries, definitions, copy_ready_lines, symbol_ranges, struct_items


def get_file_outline(path: str, tool_context: Any = None) -> str:
    """Use first, to find a function's line range before reading it."""
    res = _parse_and_outline_file(path)
    if isinstance(res, str):
        return res
    f_path, total_lines, first_doc_line, import_entries, definitions, copy_ready_lines, symbol_ranges, *rest = res

    if tool_context is not None and hasattr(tool_context, "state"):
        try:
            tool_context.state["temp:symbol_ranges"] = symbol_ranges
        except Exception:
            pass

    copy_ready_block = ["COPY-READY OUTLINE:"]
    if copy_ready_lines:
        copy_ready_block.extend(copy_ready_lines)
    else:
        copy_ready_block.append("<no classes or functions defined>")

    def assemble(include_docstrings: bool = True, include_imports: bool = True, include_detail_defs: bool = True) -> str:
        parts = [f"Outline for {f_path} (total lines: {total_lines}):\n"]
        if include_docstrings:
            parts.append(f"Module Docstring: \"{first_doc_line}\"\n")
        if include_imports and import_entries:
            parts.append(f"Imports ({len(import_entries)}):")
            parts.extend(import_entries)
            parts.append("")
        if include_detail_defs:
            if definitions:
                parts.append(f"Definitions ({len(definitions)}):")
                if include_docstrings:
                    parts.extend(definitions)
                else:
                    parts.extend([d.split(" - \"")[0] for d in definitions])
                parts.append("")
            else:
                parts.append("Definitions: <no classes or functions defined>\n")
        parts.extend(copy_ready_block)
        return "\n".join(parts)

    full_text = assemble(include_docstrings=True, include_imports=True, include_detail_defs=True)
    if len(full_text) > 5800:
        full_text = assemble(include_docstrings=False, include_imports=True, include_detail_defs=True)
    if len(full_text) > 5800:
        full_text = assemble(include_docstrings=False, include_imports=False, include_detail_defs=True)
    if len(full_text) > 5800:
        full_text = assemble(include_docstrings=False, include_imports=False, include_detail_defs=False)

    return cap_output(full_text)


def show_file_outline(path: str, tool_context: Any = None) -> str:
    """Use this when the user asks for an outline, structure or list of the functions/classes of ONE file. Its output is shown to the user as is."""
    from code_helper.tools._final_struct_registry import set_last_final_struct
    res = _parse_and_outline_file(path)
    if isinstance(res, str):
        return res
    _, _, _, _, _, copy_ready_lines, _, struct_items = res

    lines = ["COPY-READY OUTLINE:"]
    if copy_ready_lines:
        lines.extend(copy_ready_lines)
    else:
        lines.append("<no classes or functions defined>")

    output_text = cap_output("\n".join(lines))
    final_struct = {
        "kind": "outline",
        "path": path,
        "items": struct_items,
    }

    if tool_context is not None:
        state_write_ok = False
        if hasattr(tool_context, "state") and tool_context.state is not None:
            try:
                tool_context.state["temp:final_text"] = output_text
                tool_context.state["temp:final_struct"] = final_struct
                state_write_ok = True
            except Exception:
                state_write_ok = False
        if state_write_ok and hasattr(tool_context, "actions") and tool_context.actions is not None:
            try:
                tool_context.actions.skip_summarization = True
            except Exception:
                pass

    set_last_final_struct(final_struct)
    return output_text
