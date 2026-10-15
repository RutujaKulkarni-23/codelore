import ast
import difflib
from pathlib import Path
from typing import Any

from code_helper.tools._context import get_project_root, get_namespace
from code_helper.tools._paths import cap_output, wrap_untrusted_code
from code_helper.rag.scanner import scan_python_files
from code_helper.rag.search import search


def _safe_store_final_text(tool_context: Any, output_text: str, final_struct: dict[str, Any] | None = None) -> None:
    """Safely stores output_text and optional final_struct in temp state and sets skip_summarization."""
    if final_struct:
        from code_helper.tools._final_struct_registry import set_last_final_struct
        set_last_final_struct(final_struct)
    if tool_context is not None:
        state_write_ok = False
        if hasattr(tool_context, "state") and tool_context.state is not None:
            try:
                tool_context.state["temp:final_text"] = output_text
                if final_struct:
                    tool_context.state["temp:final_struct"] = final_struct
                state_write_ok = True
            except Exception:
                state_write_ok = False
        if state_write_ok and hasattr(tool_context, "actions") and tool_context.actions is not None:
            try:
                tool_context.actions.skip_summarization = True
            except Exception:
                pass


def rag_search(query: str, top_k: int = 5) -> str:
    """
    Search indexed code chunks using semantic embeddings and Pinecone vector search.
    Use this tool when looking for concepts, implementations, or functionality
    by natural language query or conceptual description.
    """
    if not isinstance(query, str) or not query.strip():
        return "ERROR: query parameter cannot be empty or blank."
    if len(query) > 200:
        return f"ERROR: query parameter length ({len(query)}) exceeds maximum limit of 200 characters."
    if top_k is None:
        top_k = 3
    elif isinstance(top_k, str):
        try:
            top_k = int(top_k.strip())
        except ValueError:
            return f"ERROR: top_k parameter must be an integer between 1 and 20, got {top_k}."
    elif not isinstance(top_k, int) or isinstance(top_k, bool):
        return f"ERROR: top_k parameter must be an integer between 1 and 20, got {top_k}."

    if top_k < 1 or top_k > 20:
        return f"ERROR: top_k parameter must be an integer between 1 and 20, got {top_k}."

    try:
        ns = get_namespace()
        results = search(
            question=query,
            top_k=top_k,
            namespace=ns,
        )
    except Exception as e:
        # Safe error without leaking keys or credentials
        err_msg = str(e).replace(ns, "<namespace>") if ns else str(e)
        return f"ERROR: Search failed due to an error: {err_msg}"

    if not results:
        return f"NOT FOUND: No matching code chunks found for '{query}'."

    lines = [f"Found {len(results)} matching code chunk(s) for '{query}':\n"]
    for idx, r in enumerate(results, start=1):
        path = r.get("path", "")
        start_line = r.get("start_line", 0)
        end_line = r.get("end_line", 0)
        symbol = r.get("symbol", "")
        score = r.get("score", 0.0)
        text = r.get("text", "")

        citation = f"{path}:{start_line}-{end_line}"
        lines.append(f"[{idx}] {citation} (symbol: {symbol}, score: {score:.4f})")
        lines.append(wrap_untrusted_code(text))
        lines.append("")

    return cap_output("\n".join(lines))


def find_symbol(name: str, tool_context: Any = None) -> str:
    """
    Locates definition locations of functions, classes, methods, or module-level constants.
    Use this tool when you know the exact or approximate name of a symbol (e.g. 'RAGConfig',
    'ensure_pinecone_index_exists', or 'Class.method') and need its line numbers.
    """
    if not isinstance(name, str) or not name.strip():
        return "ERROR: name parameter cannot be empty or blank."
    if len(name) > 200:
        return f"ERROR: name parameter length ({len(name)}) exceeds maximum limit of 200 characters."

    target_name = name.strip()
    root = get_project_root()
    scan_res = scan_python_files(root)

    # Collect all symbols: {normalized_key: list_of_symbols}
    all_symbols: list[dict[str, Any]] = []

    for rel_path in scan_res.files:
        full_path = root / rel_path
        try:
            content = full_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = full_path.read_bytes().decode("utf-8", errors="replace")

        try:
            tree = ast.parse(content, filename=rel_path)
        except SyntaxError:
            continue

        file_lines = content.splitlines()

        for node in tree.body:
            # Module-level assignments / constants
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = []
                if isinstance(node, ast.Assign):
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            targets.append(t.id)
                elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                    targets.append(node.target.id)

                for t_name in targets:
                    sig = file_lines[node.lineno - 1].strip() if node.lineno <= len(file_lines) else t_name
                    all_symbols.append({
                        "name": t_name,
                        "kind": "constant",
                        "path": rel_path,
                        "start_line": node.lineno,
                        "end_line": getattr(node, "end_lineno", node.lineno),
                        "signature": sig,
                    })

            # Top-level Functions
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sig = file_lines[node.lineno - 1].strip() if node.lineno <= len(file_lines) else f"def {node.name}..."
                try:
                    param_sig = f"{node.name}({ast.unparse(node.args)})"
                except Exception:
                    param_sig = node.name
                f_doc = ast.get_docstring(node) or ""
                first_f_doc = next((line.strip() for line in f_doc.splitlines() if line.strip()), "")[:120] if f_doc else ""
                all_symbols.append({
                    "name": node.name,
                    "kind": "function" if isinstance(node, ast.FunctionDef) else "async_function",
                    "path": rel_path,
                    "start_line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                    "signature": sig,
                    "param_sig": param_sig,
                    "doc": first_f_doc,
                })

            # Classes and methods
            elif isinstance(node, ast.ClassDef):
                sig = file_lines[node.lineno - 1].strip() if node.lineno <= len(file_lines) else f"class {node.name}..."
                c_doc = ast.get_docstring(node) or ""
                first_c_doc = next((line.strip() for line in c_doc.splitlines() if line.strip()), "")[:120] if c_doc else ""
                all_symbols.append({
                    "name": node.name,
                    "kind": "class",
                    "path": rel_path,
                    "start_line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                    "signature": sig,
                    "doc": first_c_doc,
                })

                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_full = f"{node.name}.{item.name}"
                        m_sig = file_lines[item.lineno - 1].strip() if item.lineno <= len(file_lines) else f"def {item.name}..."
                        try:
                            m_param_sig = f"{node.name}.{item.name}({ast.unparse(item.args)})"
                        except Exception:
                            m_param_sig = method_full
                        m_doc = ast.get_docstring(item) or ""
                        first_m_doc = next((line.strip() for line in m_doc.splitlines() if line.strip()), "")[:120] if m_doc else ""
                        # Store both "Method" and "Class.method"
                        all_symbols.append({
                            "name": method_full,
                            "short_name": item.name,
                            "kind": "method",
                            "path": rel_path,
                            "start_line": item.lineno,
                            "end_line": getattr(item, "end_lineno", item.lineno),
                            "signature": m_sig,
                            "param_sig": m_param_sig,
                            "doc": first_m_doc,
                        })

    # 1. Exact match
    matches = [
        s for s in all_symbols
        if s["name"] == target_name or s.get("short_name") == target_name
    ]

    # 2. Case-insensitive match if no exact match
    if not matches:
        target_lower = target_name.lower()
        matches = [
            s for s in all_symbols
            if s["name"].lower() == target_lower or s.get("short_name", "").lower() == target_lower
        ]

    # 3. If still none, find closest suggestions
    if not matches:
        known_names = list({s["name"] for s in all_symbols} | {s["short_name"] for s in all_symbols if "short_name" in s})
        close = difflib.get_close_matches(target_name, known_names, n=5, cutoff=0.4)
        if close:
            return f"NOT FOUND: Symbol '{target_name}' was not found. Did you mean: {', '.join(close)}?"
        return f"NOT FOUND: Symbol '{target_name}' was not found in the codebase."

    # Format output
    lines = [f"Found {len(matches)} definition(s) for symbol '{target_name}':\n"]
    struct_items: list[dict[str, Any]] = []
    for idx, m in enumerate(matches, start=1):
        citation = f"{m['path']}:{m['start_line']}-{m['end_line']}"
        sig_display = m.get("param_sig") or m["signature"]
        if m.get("param_sig"):
            lines.append(f"[{idx}] {m['param_sig']} - {citation}")
        else:
            lines.append(f"[{idx}] {m['kind']} {m['name']} -> {citation}")
        lines.append(f"    Signature: {m['signature']}")
        lines.append("")
        struct_items.append({
            "name": m["name"],
            "signature": sig_display,
            "path": m["path"],
            "start": m["start_line"],
            "end": m["end_line"],
            "doc": m.get("doc", ""),
        })

    output_text = cap_output("\n".join(lines))
    final_struct = {
        "kind": "symbol",
        "items": struct_items,
    }
    _safe_store_final_text(tool_context, output_text, final_struct)
    return output_text
