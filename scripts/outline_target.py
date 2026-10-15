import ast
import os
import sys
from pathlib import Path


def outline_python_file(file_path: Path):
    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source, filename=str(file_path))
    print(f"\n==================================================")
    print(f"File: {file_path.name}")
    print(f"==================================================")

    for node in tree.body:
        if isinstance(node, ast.Import):
            names = ", ".join(
                [n.name + (f" as {n.asname}" if n.asname else "") for n in node.names]
            )
            end_line = getattr(node, "end_lineno", node.lineno)
            print(f"  L{node.lineno}-L{end_line}: import {names}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            names = ", ".join(
                [n.name + (f" as {n.asname}" if n.asname else "") for n in node.names]
            )
            end_line = getattr(node, "end_lineno", node.lineno)
            print(f"  L{node.lineno}-L{end_line}: from {mod} import {names}")
        elif isinstance(node, ast.FunctionDef):
            args = [a.arg for a in node.args.args]
            end_line = getattr(node, "end_lineno", node.lineno)
            print(f"  L{node.lineno}-L{end_line}: def {node.name}({', '.join(args)})")
        elif isinstance(node, ast.ClassDef):
            end_line = getattr(node, "end_lineno", node.lineno)
            print(f"  L{node.lineno}-L{end_line}: class {node.name}")
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    args = [a.arg for a in item.args.args]
                    item_end = getattr(item, "end_lineno", item.lineno)
                    print(f"    L{item.lineno}-L{item_end}: def {item.name}({', '.join(args)})")


def outline_folder(folder_path: str):
    p = Path(folder_path)
    if not p.exists() or not p.is_dir():
        print(f"Error: Path {folder_path} does not exist or is not a directory.")
        sys.exit(1)

    py_files = sorted(list(p.glob("*.py")))
    if not py_files:
        print(f"No .py files found in {folder_path}")
        return

    for py_file in py_files:
        outline_python_file(py_file)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python outline_target.py <folder_path>")
        sys.exit(1)
    outline_folder(sys.argv[1])
