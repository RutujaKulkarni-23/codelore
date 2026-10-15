"""
Offline Tool Smoke Test for CodeLore.
Directly tests tools without AI models or agent runners.
Validates:
- find_symbol for every top-level function and class across all 5 target files.
- find_symbol("does_not_exist_xyz") -> not found and temp:final_text not set.
- analyze_imports for every function imported by another target file -> importing file:line appears.
- show_file_outline and get_file_outline for all 5 target files -> every def/class with AST range.
- Path safety -> get_file_outline rejects relative traversal and absolute paths.
- get_project_overview -> ENTRY POINT main.py present.
"""
import ast
import os
import sys
from pathlib import Path
from types import SimpleNamespace

# Ensure codelore root is on sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Target directory
TARGET_DIR = PROJECT_ROOT.parent / "targets" / "Naive_RAG"
if not TARGET_DIR.exists():
    TARGET_DIR = Path("D:/CodeLore/targets/Naive_RAG")

os.environ["CODELORE_PROJECT_ROOT"] = str(TARGET_DIR)

from code_helper.tools.search_tools import find_symbol
from code_helper.tools.architecture_tools import analyze_imports
from code_helper.tools.explain_tools import get_file_outline, show_file_outline
from code_helper.tools.onboarding_tools import get_project_overview


def run_smoke_tests() -> int:
    pass_count = 0
    fail_count = 0
    fail_details = []

    print("=" * 60)
    print("CODE LORE OFFLINE TOOL SMOKE TEST")
    print(f"Target: {TARGET_DIR}")
    print("=" * 60)

    target_files = sorted(list(TARGET_DIR.glob("*.py")))
    if len(target_files) != 5:
        print(f"WARNING: Expected 5 target files, found {len(target_files)}")

    # ---------------------------------------------------------
    # 1. find_symbol for EVERY top-level function and class
    # ---------------------------------------------------------
    print("\n[1] Testing find_symbol for all top-level definitions...")
    for fpath in target_files:
        content = fpath.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=fpath.name)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                sym_name = node.name
                expected_citation = f"{fpath.name}:{node.lineno}-{node.end_lineno}"
                out = find_symbol(sym_name)
                if expected_citation in out:
                    pass_count += 1
                else:
                    fail_count += 1
                    msg = f"FAIL find_symbol('{sym_name}'): expected '{expected_citation}' in output. Got: {out[:120]}..."
                    fail_details.append(msg)
                    print(f"  [FAIL] {sym_name} -> expected {expected_citation}")

    print(f"  find_symbol top-level definitions done.")

    # ---------------------------------------------------------
    # 2. find_symbol not-found check & final_text safety
    # ---------------------------------------------------------
    print("\n[2] Testing find_symbol('does_not_exist_xyz')...")
    ctx = SimpleNamespace(state={})
    nf_out = find_symbol("does_not_exist_xyz", tool_context=ctx)
    if "NOT FOUND" in nf_out and ctx.state.get("temp:final_text") is None:
        pass_count += 1
        print("  [PASS] not-found correctly handled without setting temp:final_text")
    else:
        fail_count += 1
        msg = f"FAIL find_symbol('does_not_exist_xyz'): output='{nf_out}', state={ctx.state}"
        fail_details.append(msg)
        print("  [FAIL] not-found handling error")

    # ---------------------------------------------------------
    # 3. analyze_imports for every function imported by another target file
    # ---------------------------------------------------------
    print("\n[3] Testing analyze_imports for cross-imported functions...")
    target_stems = {f.stem for f in target_files}
    imported_funcs: list[tuple[str, str, int]] = []

    for fpath in target_files:
        content = fpath.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=fpath.name)
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module in target_stems:
                for alias in node.names:
                    imported_funcs.append((alias.name, fpath.name, node.lineno))

    for sym_name, importing_file, line_no in imported_funcs:
        out = analyze_imports(sym_name)
        expected_ref = f"{importing_file}:{line_no}"
        if expected_ref in out and "Local symbol" in out:
            pass_count += 1
        else:
            fail_count += 1
            msg = f"FAIL analyze_imports('{sym_name}'): expected '{expected_ref}' and 'Local symbol' in output. Got: {out[:120]}..."
            fail_details.append(msg)
            print(f"  [FAIL] {sym_name} -> expected {expected_ref}")

    print(f"  analyze_imports cross-imports done ({len(imported_funcs)} tested).")

    # ---------------------------------------------------------
    # 4. show_file_outline & get_file_outline for all 5 files
    # ---------------------------------------------------------
    print("\n[4] Testing get_file_outline and show_file_outline for all 5 files...")
    for fpath in target_files:
        content = fpath.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=fpath.name)

        g_out = get_file_outline(fpath.name)
        s_out = show_file_outline(fpath.name)

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = node.decorator_list[0].lineno if node.decorator_list else node.lineno
                end = node.end_lineno
                expected_str = f"{fpath.name}:{start}-{end}"

                if expected_str in g_out and node.name in g_out:
                    pass_count += 1
                else:
                    fail_count += 1
                    msg = f"FAIL get_file_outline('{fpath.name}'): missing '{expected_str}' or '{node.name}'"
                    fail_details.append(msg)
                    print(f"  [FAIL] get_file_outline({fpath.name}) for {node.name}")

                if expected_str in s_out and node.name in s_out:
                    pass_count += 1
                else:
                    fail_count += 1
                    msg = f"FAIL show_file_outline('{fpath.name}'): missing '{expected_str}' or '{node.name}'"
                    fail_details.append(msg)
                    print(f"  [FAIL] show_file_outline({fpath.name}) for {node.name}")

    print("  file outlines done.")

    # ---------------------------------------------------------
    # 5. Path safety checks
    # ---------------------------------------------------------
    print("\n[5] Testing Path safety on get_file_outline...")
    trav_res = get_file_outline("../x.py")
    if "ERROR:" in trav_res:
        pass_count += 1
        print("  [PASS] Traversal '../x.py' rejected.")
    else:
        fail_count += 1
        msg = f"FAIL Path safety: '../x.py' was not rejected. Got: {trav_res}"
        fail_details.append(msg)
        print("  [FAIL] Traversal '../x.py' was not rejected.")

    abs_res = get_file_outline("C:/temp/some_file.py")
    if "ERROR:" in abs_res:
        pass_count += 1
        print("  [PASS] Absolute path 'C:/temp/some_file.py' rejected.")
    else:
        fail_count += 1
        msg = f"FAIL Path safety: absolute path was not rejected. Got: {abs_res}"
        fail_details.append(msg)
        print("  [FAIL] Absolute path was not rejected.")

    # ---------------------------------------------------------
    # 6. get_project_overview: ENTRY POINT main.py present
    # ---------------------------------------------------------
    print("\n[6] Testing get_project_overview for ENTRY POINT...")
    overview = get_project_overview()
    if "ENTRY POINT: main.py" in overview and "--index" in overview:
        pass_count += 1
        print("  [PASS] ENTRY POINT: main.py and --index present.")
    else:
        fail_count += 1
        msg = f"FAIL get_project_overview: missing 'ENTRY POINT: main.py' or '--index'. Got: {overview[:150]}..."
        fail_details.append(msg)
        print("  [FAIL] get_project_overview missing ENTRY POINT or --index.")

    # ---------------------------------------------------------
    # Summary
    # ---------------------------------------------------------
    total = pass_count + fail_count
    print("\n" + "=" * 60)
    print("TOOL SMOKE TEST SUMMARY")
    print(f"Total Checks: {total} | PASSED: {pass_count} | FAILED: {fail_count}")
    if fail_details:
        print("\nFAILURES:")
        for fd in fail_details:
            print(f"  - {fd}")
    else:
        print("ALL OFFLINE TOOL SMOKE TESTS PASSED PERFECTLY!")
    print("=" * 60)

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(run_smoke_tests())
