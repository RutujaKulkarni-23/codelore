import ast
import os
from pathlib import Path
from typing import Any

from code_helper.tools._context import get_project_root
from code_helper.tools._paths import cap_output
from code_helper.rag.scanner import scan_python_files, EXCLUDED_DIRS
from code_helper.rag.secrets_mask import mask_secrets


def get_project_overview() -> str:
    """
    Generate a structural project overview including file tree, entry points, CLI flags,
    dependencies, README status, and top-level data files.
    Use this tool to orient yourself when first exploring a project or onboarding to it.
    """
    root = get_project_root()
    if not root.exists() or not root.is_dir():
        return f"ERROR: Project root '{root}' does not exist or is not a directory."

    # 1. Python files scan
    scan_res = scan_python_files(root)
    total_py_files = len(scan_res.files)

    # 2. Depth-limited file tree (up to depth 2)
    tree_lines = []
    data_files = []

    def _walk_tree(dir_path: Path, current_depth: int, max_depth: int = 2) -> None:
        if current_depth > max_depth:
            return
        try:
            entries = sorted(dir_path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except Exception:
            return

        for e in entries:
            name = e.name
            if name.startswith(".") or name in EXCLUDED_DIRS:
                continue

            rel = e.relative_to(root).as_posix()
            indent = "  " * current_depth
            if e.is_dir():
                tree_lines.append(f"{indent}[dir]  {name}/")
                _walk_tree(e, current_depth + 1, max_depth)
            else:
                tree_lines.append(f"{indent}[file] {name}")
                # Track top-level data files without reading contents
                if current_depth == 1 and name.lower().endswith((".json", ".csv", ".txt", ".parquet", ".db", ".sqlite")):
                    data_files.append(rel)

    _walk_tree(root, 1)

    # 3. Entry points & CLI flags
    entry_points: list[str] = []
    cli_flags: list[dict[str, Any]] = []

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

        # Look for if __name__ == "__main__"
        has_main_guard = False
        for node in tree.body:
            if isinstance(node, ast.If):
                test = node.test
                if isinstance(test, ast.Compare):
                    left = test.left
                    if isinstance(left, ast.Name) and left.id == "__name__":
                        for comp in test.comparators:
                            if isinstance(comp, ast.Constant) and comp.value == "__main__":
                                has_main_guard = True

        if has_main_guard:
            entry_points.append(rel_path)

        # Look for parser.add_argument(...)
        for subnode in ast.walk(tree):
            if isinstance(subnode, ast.Call):
                func = subnode.func
                if isinstance(func, ast.Attribute) and func.attr == "add_argument":
                    flag_args = []
                    for arg in subnode.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            flag_args.append(arg.value)
                    help_text = ""
                    for kw in subnode.keywords:
                        if kw.arg == "help" and isinstance(kw.value, ast.Constant):
                            help_text = str(kw.value.value)

                    if flag_args:
                        cli_flags.append({
                            "file": rel_path,
                            "line": subnode.lineno,
                            "flags": flag_args,
                            "help": help_text,
                        })

    # 4. Dependency files
    dep_summary: list[str] = []
    candidate_deps = ["requirements.txt", "requirements-dev.txt", "pyproject.toml", "setup.cfg"]
    for c_name in candidate_deps:
        p = root / c_name
        if p.exists() and p.is_file():
            try:
                raw_lines = p.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                raw_lines = p.read_bytes().decode("utf-8", errors="replace").splitlines()

            first_40 = "\n".join(raw_lines[:40])
            masked_content, _ = mask_secrets(first_40)
            dep_summary.append(f"File '{c_name}' (showing first 40 lines):\n{masked_content}")

    # 5. README presence
    readme_files = list(root.glob("README*"))
    readme_status = f"README found: {readme_files[0].name}" if readme_files else "No README found"

    # Assemble report
    out: list[str] = [
        f"Project Overview for {root.name} ({total_py_files} Python file(s)):\n",
        f"1. Documentation: {readme_status}\n",
        f"2. File Tree (depth limit 2):",
    ]
    out.extend(tree_lines[:40])
    if len(tree_lines) > 40:
        out.append("   ... (additional files omitted)")
    out.append("")

    out.append(f"3. Entry Points ({len(entry_points)} found):")
    if entry_points:
        for ep in entry_points:
            out.append(f"  - {ep} (contains '__main__' guard)")
    else:
        out.append("  (No entry points found)")
    out.append("")

    out.append(f"4. Command-Line Flags ({len(cli_flags)} found):")
    if cli_flags:
        for fl in cli_flags:
            flags_str = ", ".join(fl["flags"])
            help_str = f" - {fl['help']}" if fl['help'] else ""
            out.append(f"  - {fl['file']}:L{fl['line']} -> {flags_str}{help_str}")
    else:
        out.append("  (No CLI arguments found)")
    out.append("")

    out.append(f"5. Top-Level Data Files ({len(data_files)} found):")
    if data_files:
        for df in data_files:
            out.append(f"  - {df}")
    else:
        out.append("  (No top-level data files found)")
    out.append("")

    out.append(f"6. Dependency Files ({len(dep_summary)} found):")
    if dep_summary:
        out.extend(dep_summary)
    else:
        out.append("  (No standard dependency files like requirements.txt found)")

    return cap_output("\n".join(out))
