import ast
import os
from pathlib import Path
from typing import Any

from code_helper.tools._context import get_project_root
from code_helper.tools._paths import cap_output
from code_helper.rag.scanner import scan_python_files, EXCLUDED_DIRS
from code_helper.rag.secrets_mask import mask_secrets



def _safe_store_final_text(tool_context: Any, output_text: str) -> None:
    """Safely stores output_text in temp:final_text state and sets skip_summarization."""
    if tool_context is not None:
        state_write_ok = False
        if hasattr(tool_context, "state") and tool_context.state is not None:
            try:
                tool_context.state["temp:final_text"] = output_text
                state_write_ok = True
            except Exception:
                state_write_ok = False
        if state_write_ok and hasattr(tool_context, "actions") and tool_context.actions is not None:
            try:
                tool_context.actions.skip_summarization = True
            except Exception:
                pass


def get_project_overview(tool_context: Any = None) -> str:
    """
    Generate a structural project overview including entry point, how to run,
    reading order, data files, dependency files, and documentation.
    Use this tool to orient yourself when first exploring a project or onboarding to it.
    """
    root = get_project_root()
    if not root.exists() or not root.is_dir():
        return f"ERROR: Project root '{root}' does not exist or is not a directory."

    # 1. Python files scan
    scan_res = scan_python_files(root)
    total_py_files = len(scan_res.files)

    # 2. File categorisation
    data_dir = root / "data"
    data_files: list[str] = []
    if data_dir.exists() and data_dir.is_dir():
        for p in sorted(data_dir.rglob("*")):
            if p.is_file():
                data_files.append(p.relative_to(root).as_posix())

    dep_candidates = ["requirements.txt", "requirements-dev.txt", "pyproject.toml", "setup.cfg", "setup.py", "Pipfile"]
    dep_files = [c for c in dep_candidates if (root / c).is_file()]

    doc_files = [p.relative_to(root).as_posix() for p in sorted(root.glob("*.md")) if p.is_file()]

    # 3. Entry points & CLI flags via AST
    entry_candidates_main_guard: list[str] = []
    entry_candidates_both: list[str] = []
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

        has_main_guard = False
        has_argparse = False
        for node in tree.body:
            if isinstance(node, ast.If):
                test = node.test
                if isinstance(test, ast.Compare):
                    left = test.left
                    if isinstance(left, ast.Name) and left.id == "__name__":
                        for comp in test.comparators:
                            if isinstance(comp, ast.Constant) and comp.value == "__main__":
                                has_main_guard = True
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for a in node.names:
                        if a.name == "argparse":
                            has_argparse = True
                elif isinstance(node, ast.ImportFrom) and node.module == "argparse":
                    has_argparse = True

        if has_main_guard:
            entry_candidates_main_guard.append(rel_path)

        for subnode in ast.walk(tree):
            if isinstance(subnode, ast.Call):
                func = subnode.func
                if isinstance(func, ast.Attribute) and func.attr == "add_argument":
                    has_argparse = True
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

        if has_main_guard and has_argparse:
            entry_candidates_both.append(rel_path)

    chosen_entry = None
    if entry_candidates_both:
        chosen_entry = "main.py" if "main.py" in entry_candidates_both else entry_candidates_both[0]
    elif entry_candidates_main_guard:
        chosen_entry = "main.py" if "main.py" in entry_candidates_main_guard else entry_candidates_main_guard[0]

    also_runnable = [ep for ep in entry_candidates_main_guard if ep != chosen_entry]

    # Extract stages from chosen_entry or other files
    stages: list[str] = []
    if chosen_entry and (root / chosen_entry).exists():
        try:
            m_text = (root / chosen_entry).read_text(encoding="utf-8")
        except Exception:
            m_text = (root / chosen_entry).read_bytes().decode("utf-8", errors="replace")
        for line in m_text.splitlines():
            if "[Stage " in line:
                for part in line.split("[Stage "):
                    if "]" in part:
                        st_num, rest = part.split("]", 1)
                        st_name = rest.split("-->")[0].split("\\n")[0].split('")')[0].split("')")[0].strip()
                        if st_num.strip().isdigit() and st_name:
                            stages.append(f"Stage {st_num.strip()}: {st_name}")

    # Build output
    lines: list[str] = ["Here is what I can tell you about this codebase:\n"]

    # Section 1: What it is
    lines.append("What it is:")
    if stages:
        lines.append("The entry point prints these stages:")
        for st in stages:
            lines.append(f"  - {st}")
    else:
        lines.append(f"A Python project with {total_py_files} Python file(s).")
    lines.append("")

    # Section 2: Start here
    lines.append("Start here:")
    if chosen_entry:
        lines.append(f"  ENTRY POINT: {chosen_entry}")
    if also_runnable:
        lines.append(f"  Also runnable as scripts: {', '.join(also_runnable)}")
    lines.append("")

    # Section 3: How to run
    lines.append("How to run:")
    how_to_run_flags = []
    if chosen_entry:
        target_flags = [fl for fl in cli_flags if fl["file"] == chosen_entry]
        if not target_flags and cli_flags:
            target_flags = cli_flags
        if target_flags:
            for fl in target_flags:
                for f_name in fl["flags"]:
                    if f_name.startswith("-"):
                        how_to_run_flags.append(f"python {chosen_entry} {f_name}")
    if how_to_run_flags:
        for cmd in how_to_run_flags:
            lines.append(f"  - {cmd}")
    elif chosen_entry:
        lines.append(f"  - python {chosen_entry}")
    else:
        lines.append("  (No runnable entry point found)")
    lines.append("")

    # Section 4: Read the files in this order
    lines.append("Read the files in this order:")
    reading_order = []
    if "config.py" in scan_res.files:
        reading_order.append("config.py")
    for f in scan_res.files:
        if f not in reading_order and f != chosen_entry:
            reading_order.append(f)
    if chosen_entry and chosen_entry not in reading_order and chosen_entry in scan_res.files:
        reading_order.append(chosen_entry)

    for idx, f in enumerate(reading_order, 1):
        f_doc_line = ""
        full_f = root / f
        try:
            f_content = full_f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            f_content = full_f.read_bytes().decode("utf-8", errors="replace")
        try:
            f_tree = ast.parse(f_content, filename=f)
            mod_doc = ast.get_docstring(f_tree)
            if mod_doc:
                first_non_empty = next((l.strip() for l in mod_doc.splitlines() if l.strip()), "")
                if first_non_empty:
                    base_name = Path(f).name
                    for prefix_cand in (f"{f} — ", f"{base_name} — ", f"{f} - ", f"{base_name} - ", f"{f} – ", f"{base_name} – "):
                        if first_non_empty.startswith(prefix_cand):
                            first_non_empty = first_non_empty[len(prefix_cand):].strip()
                            break
                    f_doc_line = f" - {first_non_empty[:100]}"
        except Exception:
            pass

        lines.append(f"  {idx}. {f}{f_doc_line}")
    lines.append("")

    # Section 5: Other files
    lines.append("Other files:")
    data_str = ", ".join(data_files) if data_files else "None"
    dep_str = ", ".join(dep_files) if dep_files else "None"
    doc_str = ", ".join(doc_files) if doc_files else "None"
    lines.append(f"  - Data files (under data/): {data_str}")
    lines.append(f"  - Dependency files: {dep_str}")
    lines.append(f"  - Documentation: {doc_str}")

    output_text = cap_output("\n".join(lines))
    _safe_store_final_text(tool_context, output_text)
    return output_text

