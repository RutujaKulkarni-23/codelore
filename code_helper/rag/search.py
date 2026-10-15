import sys
from typing import Any
from pathlib import Path

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from code_helper.settings import load_settings, Settings
from code_helper.rag.embedder import embed_query
from code_helper.rag.vector_store import get_index, query as query_vector_store


def search(
    question: str,
    top_k: int | None = None,
    min_score: float | None = None,
    namespace: str | None = None,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """
    Embeds question using NVIDIA NIM and searches Pinecone.
    Returns list of dicts with:
      - path
      - symbol
      - start_line
      - end_line
      - score
      - text
    Rejects empty or over-long questions (exceeding MAX_QUERY_CHARS).
    """
    cfg = settings or load_settings()

    if not question or not question.strip():
        raise ValueError("Search question cannot be empty or whitespace.")

    if len(question) > cfg.max_query_chars:
        raise ValueError(
            f"Question length ({len(question)}) exceeds max_query_chars ({cfg.max_query_chars})."
        )

    k = top_k if top_k is not None else cfg.top_k
    score_threshold = min_score if min_score is not None else cfg.min_score
    ns = namespace if namespace is not None else cfg.pinecone_namespace

    # 1. Embed query
    query_vector = embed_query(text=question, settings=cfg)

    # 2. Query Pinecone
    index = get_index(settings=cfg, allow_create=False)
    matches = query_vector_store(
        index=index,
        vector=query_vector,
        top_k=k,
        namespace=ns,
        min_score=score_threshold,
    )

    results = []
    for m in matches:
        results.append({
            "path": m.get("path", ""),
            "symbol": m.get("symbol", ""),
            "start_line": m.get("start_line", 0),
            "end_line": m.get("end_line", 0),
            "score": m.get("score", 0.0),
            "text": m.get("text", ""),
        })

    return results


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m code_helper.rag.search \"question\" [top_k] [min_score]")
        sys.exit(1)

    question = sys.argv[1]
    top_k = int(sys.argv[2]) if len(sys.argv) > 2 else None
    min_score = float(sys.argv[3]) if len(sys.argv) > 3 else None

    try:
        results = search(question=question, top_k=top_k, min_score=min_score)
        print(f"Query: \"{question}\" (Results: {len(results)})\n")
        if not results:
            print("No matching chunks found.")
            return

        for idx, r in enumerate(results, start=1):
            path = r["path"]
            start_line = r["start_line"]
            end_line = r["end_line"]
            symbol = r["symbol"]
            score = r["score"]
            text = r["text"]
            # Short preview: first non-header lines
            lines = [l for l in text.splitlines() if not l.startswith("# file:")]
            preview = " ".join([l.strip() for l in lines[:4] if l.strip()])
            if len(preview) > 120:
                preview = preview[:117] + "..."

            print(f"[{idx}] {path}:{start_line}-{end_line} | symbol: {symbol} | score: {score:.4f}")
            print(f"    Preview: {preview}\n")
    except Exception as e:
        print(f"Error during search: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
