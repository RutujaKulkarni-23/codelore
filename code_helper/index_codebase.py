import argparse
import sys
from pathlib import Path

# Ensure project root is in sys.path so running directly as `python code_helper/index_codebase.py` works
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from code_helper.settings import load_settings
from code_helper.rag.scanner import scan_python_files
from code_helper.rag.chunker import chunk_source_file
from code_helper.rag.secrets_mask import mask_secrets
from code_helper.rag.embedder import embed_documents
from code_helper.rag.vector_store import get_index, upsert_chunks, wait_until_count, query


def index_codebase(
    strategy: str | None = None,
    namespace: str | None = None,
    dry_run: bool = False,
    auto_yes: bool = False,
) -> None:
    settings = load_settings()
    target_path = settings.target_project_path
    chosen_strategy = strategy or settings.chunk_strategy
    chosen_namespace = namespace or settings.pinecone_namespace

    print(f"=== Starting Codebase Indexing Pipeline ===")
    print(f"Target path: {target_path}")
    print(f"Strategy: {chosen_strategy}")
    print(f"Namespace: {chosen_namespace}")
    print(f"Dry run: {dry_run}")

    # Stage 1: Scan
    scan_res = scan_python_files(
        target_path,
        max_files=settings.max_files,
        max_file_bytes=settings.max_file_bytes,
    )
    print(f"\n[1. Scan] Scanned Python files: {len(scan_res.files)}")
    if scan_res.skipped:
        print(f"          Skipped files: {len(scan_res.skipped)}")
        for path, reason in scan_res.skipped:
            print(f"            - {path}: {reason}")
    else:
        print(f"          Skipped files: 0")

    # Stage 2: Chunk
    all_chunks = []
    for rel_path in scan_res.files:
        full_path = target_path / rel_path
        try:
            content = full_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = full_path.read_bytes().decode("utf-8", errors="replace")

        chunks = chunk_source_file(
            source_text=content,
            path=rel_path,
            strategy=chosen_strategy,
            max_chunk_lines=settings.max_chunk_lines,
            chunk_overlap_lines=settings.chunk_overlap_lines,
            max_chunk_chars=settings.max_chunk_chars,
        )
        all_chunks.extend(chunks)

    print(f"\n[2. Chunk] Generated chunks: {len(all_chunks)}")

    # Stage 3: Mask Secrets
    masked_chunks = []
    total_masked_secrets = 0
    for c in all_chunks:
        masked_text, count = mask_secrets(c.text)
        total_masked_secrets += count
        c.text = masked_text
        masked_chunks.append(c)

    print(f"\n[3. Secrets Masking] Total masked secrets found: {total_masked_secrets}")

    # Estimate embedding calls
    batch_size = max(1, settings.embed_batch_size)
    num_embed_calls = (len(masked_chunks) + batch_size - 1) // batch_size if masked_chunks else 0
    print(f"\n[4. Planning] Required embedding calls: {num_embed_calls} (batch size {batch_size})")

    if dry_run:
        print("\n--- DRY RUN SUMMARY ---")
        print(f"Chunks that would be sent: {len(masked_chunks)}")
        print(f"Embedding API calls that would be made: {num_embed_calls}")
        print(f"Pinecone target index: {settings.pinecone_index_name}")
        print(f"Pinecone target namespace: {chosen_namespace}")
        print("Dry run completed. No remote API calls were made.")
        return

    # User confirmation prompt
    prompt_msg = f"About to send {len(masked_chunks)} chunks from {target_path} to NVIDIA (embeddings) and Pinecone (storage). Continue? [y/N]: "
    if not auto_yes:
        ans = input(prompt_msg).strip().lower()
        if ans != "y":
            print("Aborted by user.")
            return
    else:
        print(f"About to send {len(masked_chunks)} chunks from {target_path} to NVIDIA (embeddings) and Pinecone (storage). [auto-confirmed via --yes]")

    # Stage 4: Embed via NVIDIA NIM
    texts = [c.text for c in masked_chunks]
    print(f"\n[5. Embed] Calling NVIDIA NIM embeddings ({settings.nvidia_embed_model})...")
    vectors = embed_documents(texts, settings=settings)
    print(f"          Successfully embedded {len(vectors)} vectors (dimension {len(vectors[0]) if vectors else 0}).")

    # Stage 5: Store in Pinecone
    print(f"\n[6. Store] Connecting to Pinecone index '{settings.pinecone_index_name}'...")
    index = get_index(settings=settings, allow_create=True)

    print(f"          Upserting {len(vectors)} vectors into namespace '{chosen_namespace}'...")
    upserted_count = upsert_chunks(
        index=index,
        chunks=masked_chunks,
        vectors=vectors,
        namespace=chosen_namespace,
        settings=settings,
        batch_size=100,
    )
    print(f"          Upserted {upserted_count} records.")

    # Stage 6: Wait for consistency & Validate
    print(f"\n[7. Validation] Waiting for Pinecone namespace '{chosen_namespace}' count to reach {len(masked_chunks)}...")
    synced = wait_until_count(
        index=index,
        namespace=chosen_namespace,
        expected_count=len(masked_chunks),
        timeout=30.0,
        poll_interval=1.0,
    )
    if not synced:
        print("          Warning: Namespace vector count did not sync before timeout (Pinecone is eventually consistent).")
    else:
        print("          Namespace count verified.")

    # Validation query
    if vectors:
        print("          Running validation query...")
        val_results = query(
            index=index,
            vector=vectors[0],
            top_k=1,
            namespace=chosen_namespace,
            min_score=0.0,
        )
        if val_results and len(val_results) >= 1:
            print("          Validation query matched at least 1 record.")
            print("\nREADY")
        else:
            print("          Validation query returned 0 matches.")
    else:
        print("READY")


def main() -> None:
    parser = argparse.ArgumentParser(description="Index codebase into Pinecone using NVIDIA NIM embeddings.")
    parser.add_argument("--dry-run", action="store_true", help="Perform dry run without calling remote APIs")
    parser.add_argument("--strategy", choices=["ast_hybrid", "fixed_window"], default=None, help="Chunking strategy")
    parser.add_argument("--namespace", default=None, help="Pinecone namespace to upsert vectors into")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")

    args = parser.parse_args()
    index_codebase(
        strategy=args.strategy,
        namespace=args.namespace,
        dry_run=args.dry_run,
        auto_yes=args.yes,
    )


if __name__ == "__main__":
    main()
