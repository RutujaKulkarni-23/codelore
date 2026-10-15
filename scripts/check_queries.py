import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from code_helper.rag.search import search

queries = [
    # EVAL_01 queries
    "get_rag_config default top_k value config.py",
    "get_rag_config default top_k config.py",
    "get_rag_config top_k config.py",
    # EVAL_02 queries
    "function embed_query parameters",
    "embed_query",
]

for q in queries:
    res = search(q, top_k=3, min_score=0.0)
    print(f"Query: {q}")
    for i, r in enumerate(res, 1):
        print(f"  [{i}] {r['path']}:{r['start_line']}-{r['end_line']} | symbol: {r['symbol']} | score: {r['score']:.4f}")
    print("-" * 60)
