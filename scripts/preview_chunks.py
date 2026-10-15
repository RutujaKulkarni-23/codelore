import argparse
import sys
from pathlib import Path

# Ensure codelore root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from code_helper.rag.scanner import scan_python_files
from code_helper.rag.chunker import chunk_source_file


def preview_chunks(root_dir: str, strategy: str = "ast_hybrid", show_text: bool = False):
    root_path = Path(root_dir)
    print(f"Scanning Python files in: {root_path}")
    scan_res = scan_python_files(root_path)

    if scan_res.skipped:
        print(f"Skipped items ({len(scan_res.skipped)}):")
        for p, r in scan_res.skipped:
            print(f"  - {p}: {r}")

    print(f"\nDiscovered {len(scan_res.files)} files. Chunking with strategy: '{strategy}'\n")
    print(f"{'Path':<22} | {'Symbol':<24} | {'Kind':<8} | {'Lines':<9} | {'Chars':<6} | {'Chunk ID':<32}")
    print("-" * 115)

    per_file_counts: dict[str, int] = {}
    total_chunks = 0

    for rel_path in scan_res.files:
        full_path = root_path / rel_path
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()

        chunks = chunk_source_file(
            source_text=content,
            path=rel_path,
            strategy=strategy,
        )
        per_file_counts[rel_path] = len(chunks)
        total_chunks += len(chunks)

        for c in chunks:
            line_str = f"L{c.start_line}-L{c.end_line}"
            print(
                f"{c.path:<22} | {c.symbol:<24} | {c.kind:<8} | {line_str:<9} | {len(c.text):<6} | {c.id:<32}"
            )
            if show_text:
                print(f"    --> Header: {c.text.splitlines()[0]}")

    print("-" * 115)
    print("\nSummary per file:")
    for f, count in per_file_counts.items():
        print(f"  {f:<25}: {count} chunks")
    print(f"Total chunks generated: {total_chunks}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Preview chunks generated from target Python files.")
    parser.add_argument("root", type=str, help="Root directory to scan and chunk.")
    parser.add_argument(
        "--strategy",
        type=str,
        default="ast_hybrid",
        choices=["ast_hybrid", "fixed_window"],
        help="Chunking strategy to use (default: ast_hybrid).",
    )
    parser.add_argument(
        "--show-text",
        action="store_true",
        help="Display the header line for each chunk.",
    )
    args = parser.parse_args()
    preview_chunks(args.root, strategy=args.strategy, show_text=args.show_text)
