import ast
import sys
from pathlib import Path
from typing import Any

from code_helper.tools._context import get_project_root
from code_helper.tools._paths import cap_output
from code_helper.rag.scanner import scan_python_files


def _normalize_module_name(rel_path: str) -> str:
    """Converts relative path to module name, e.g. 'foo/bar.py' -> 'foo.bar'."""
    p = Path(rel_path)
    if p.name == "__init__.py":
        return ".".join(p.parent.parts)
    parts = list(p.parent.parts) + [p.stem]
    return ".".join(parts)


def _safe_store_final_text(tool_context: Any, output_text: str, final_struct: dict[str, Any] | None = None) -> None:
    """Safely stores output_text in temp:final_text state and sets skip_summarization."""
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


def analyze_imports(module_name: str = "", tool_context: Any = None) -> str:
    """
    Analyzes Python module dependencies and imports across the project.
    Use this tool to inspect the project-wide import graph, determine who imports a module,
    or see what a specific module imports (internal vs stdlib vs third-party).
    """
    if module_name is None:
        module_name = ""
    elif not isinstance(module_name, str):
        return "ERROR: module_name parameter must be a string."
    if len(module_name) > 200:
        return f"ERROR: module_name parameter length ({len(module_name)}) exceeds maximum limit of 200 characters."

    query_mod = module_name.strip()
    root = get_project_root()
    scan_res = scan_python_files(root)

    # Known internal modules
    internal_mods = set()
    file_to_mod: dict[str, str] = {}
    mod_to_file: dict[str, str] = {}

    for rel_path in scan_res.files:
        mod = _normalize_module_name(rel_path)
        internal_mods.add(mod)
        internal_mods.add(Path(rel_path).stem)  # simple module name
        file_to_mod[rel_path] = mod
        mod_to_file[mod] = rel_path
        mod_to_file[Path(rel_path).stem] = rel_path

    stdlib_names = getattr(sys, "stdlib_module_names", set())

    # Build graph:
    # file_imports[rel_path] = list of {"imported": name, "line": line, "type": internal|stdlib|third_party}
    file_imports: dict[str, list[dict[str, Any]]] = {}
    all_third_party: set[str] = set()
    local_definitions: dict[str, str] = {}

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

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                local_definitions[node.name] = Path(rel_path).stem
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                if isinstance(node, ast.Assign):
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            local_definitions[t.id] = Path(rel_path).stem
                elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                    local_definitions[node.target.id] = Path(rel_path).stem

        imports_in_file: list[dict[str, Any]] = []

        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_name = alias.name.split(".")[0]
                    imp_type = "third_party"
                    if alias.name in internal_mods or top_name in internal_mods:
                        imp_type = "internal"
                    elif top_name in stdlib_names:
                        imp_type = "stdlib"
                    else:
                        all_third_party.add(top_name)

                    imports_in_file.append({
                        "name": alias.name,
                        "symbols": [alias.name],
                        "rep": alias.name,
                        "line": node.lineno,
                        "end_line": getattr(node, "end_lineno", node.lineno),
                        "type": imp_type,
                    })

            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                top_name = mod.split(".")[0] if mod else ""
                imp_type = "third_party"
                if node.level > 0:
                    imp_type = "internal"
                elif mod in internal_mods or top_name in internal_mods:
                    imp_type = "internal"
                elif top_name in stdlib_names:
                    imp_type = "stdlib"
                else:
                    if top_name:
                        all_third_party.add(top_name)

                symbol_list = [a.name for a in node.names]
                if imp_type == "internal" and mod:
                    for s in symbol_list:
                        if s not in local_definitions:
                            local_definitions[s] = mod

                imported_names = ", ".join(symbol_list)
                full_rep = f"{mod} ({imported_names})" if mod else imported_names
                imports_in_file.append({
                    "name": mod or imported_names,
                    "symbols": symbol_list,
                    "module": mod,
                    "rep": full_rep,
                    "line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                    "type": imp_type,
                })

        file_imports[rel_path] = imports_in_file


    # Mode 1: Empty or project root name -> Full internal graph + third-party summary
    is_full_project_query = (
        not query_mod
        or query_mod.lower() in ("", root.name.lower(), root.stem.lower(), "all", "project", ".")
    )
    if is_full_project_query:
        lines = [f"Project Import Analysis ({len(scan_res.files)} Python files):\n"]
        lines.append("Internal Dependency Graph:")
        for rel_path, imps in sorted(file_imports.items()):
            internal_targets = [f"{i['name']} ({rel_path}:{i['line']}-{i['end_line']})" for i in imps if i["type"] == "internal"]
            if internal_targets:
                lines.append(f"  - {rel_path} -> {', '.join(internal_targets)}")
            else:
                lines.append(f"  - {rel_path} -> (no internal imports)")

        lines.append("")
        sorted_tp = sorted(all_third_party)
        lines.append(f"Third-Party Dependencies ({len(sorted_tp)}): {', '.join(sorted_tp) if sorted_tp else 'None'}")
        output_text = cap_output("\n".join(lines))
        final_struct = {
            "kind": "imports",
            "target": query_mod or root.name,
            "defined_in": None,
            "importers": [],
        }
        _safe_store_final_text(tool_context, output_text, final_struct)
        return output_text

    # Mode 2: Specific module_name or symbol name
    target_stem = Path(query_mod).stem
    is_internal = query_mod in internal_mods or target_stem in internal_mods

    # Find who imports this module or symbol
    importers: list[tuple[str, int, int]] = []
    matched_as_symbol = False
    for rel_path, imps in file_imports.items():
        for i in imps:
            imp_name = i["name"]
            imp_top = imp_name.split(".")[0]
            symbols = i.get("symbols", [])
            if query_mod in symbols:
                importers.append((rel_path, i["line"], i["end_line"]))
                matched_as_symbol = True
            elif imp_name == query_mod or imp_name == target_stem or imp_top == target_stem:
                importers.append((rel_path, i["line"], i["end_line"]))

    # Find what this module imports (if it is an internal file)
    direct_imports: list[dict[str, Any]] = []
    matched_rel_path = mod_to_file.get(query_mod) or mod_to_file.get(target_stem)
    if matched_rel_path and matched_rel_path in file_imports:
        direct_imports = file_imports[matched_rel_path]

    lines = [f"Import Analysis for module '{query_mod}':\n"]
    if is_internal and matched_rel_path:
        lines.append(f"Module Type: Internal file ({matched_rel_path})\n")
    elif query_mod in local_definitions:
        lines.append(f"Module Type: Local symbol (defined in {local_definitions[query_mod]})\n")
    else:
        m_type = "Standard Library" if query_mod in stdlib_names else "Third-party / External"
        lines.append(f"Module Type: {m_type}\n")

    lines.append(f"Imported by ({len(importers)} reference(s)):")
    importers_struct: list[dict[str, Any]] = []
    if importers:
        for f_path, l_no, end_l in sorted(importers):
            lines.append(f"  - {f_path}:{l_no}-{end_l}")
            stmt = ""
            try:
                full_f = root / f_path
                content = full_f.read_text(encoding="utf-8")
                f_lines = content.splitlines()
                if 1 <= l_no <= len(f_lines):
                    stmt = f_lines[l_no - 1].strip()
            except Exception:
                stmt = ""
            importers_struct.append({
                "path": f_path,
                "line": l_no,
                "statement": stmt,
            })
    else:
        lines.append("  (No files in the project import this module)")

    if is_internal and matched_rel_path:
        lines.append(f"\nWhat '{matched_rel_path}' imports ({len(direct_imports)} statement(s)):")
        if direct_imports:
            for di in direct_imports:
                lines.append(f"  - {matched_rel_path}:{di['line']}-{di['end_line']}: {di.get('rep', di['name'])} [{di['type']}]")
        else:
            lines.append("  (No import statements)")

    output_text = cap_output("\n".join(lines))
    has_results = bool(importers or direct_imports)
    defined_in_val = None
    if query_mod in local_definitions:
        defined_in_val = local_definitions[query_mod]
        if not defined_in_val.endswith(".py"):
            defined_in_val = f"{defined_in_val}.py"
    elif is_internal and matched_rel_path:
        defined_in_val = matched_rel_path

    final_struct = {
        "kind": "imports",
        "target": query_mod,
        "defined_in": defined_in_val,
        "importers": importers_struct,
    }
    if has_results:
        _safe_store_final_text(tool_context, output_text, final_struct)
    return output_text
