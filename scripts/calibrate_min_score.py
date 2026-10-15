"""
Calibration script for MIN_SCORE in CodeLore.
Runs embedding-only queries against Pinecone (no chat model) for answerable
and not-found questions from docs/target_analysis.md section h.
Outputs scores and generates eval_runs/min_score_calibration.md.
"""
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from code_helper.rag.search import search
from code_helper.settings import load_settings

QUESTIONS = [
    # Answerable questions (from docs/target_analysis.md section h)
    {
        "id": "A1",
        "question": "What are the top-level module dependencies between the 5 Python files in Naive_RAG?",
        "expected": "answerable",
        "expected_files": ["main.py", "indexer.py", "query_pipeline.py", "vector_store.py"],
    },
    {
        "id": "A2",
        "question": "What are the 8 architectural stages of the RAG pipeline described in Naive_RAG?",
        "expected": "answerable",
        "expected_files": ["main.py", "Day4_Naive_RAG_Project_Build_Spec.md"],
    },
    {
        "id": "A3",
        "question": "Where is the default Pinecone index name defined, and what is its value?",
        "expected": "answerable",
        "expected_files": ["config.py"],
    },
    {
        "id": "A4",
        "question": "What chunk size and chunk overlap values are used by default when chunking documents?",
        "expected": "answerable",
        "expected_files": ["indexer.py", "config.py"],
    },
    {
        "id": "A5",
        "question": "How does chunk_document in indexer.py partition text, and what metadata does each chunk receive?",
        "expected": "answerable",
        "expected_files": ["indexer.py"],
    },
    {
        "id": "A6",
        "question": "Can you provide an outline of indexer.py and list its classes and functions?",
        "expected": "answerable",
        "expected_files": ["indexer.py"],
    },
    {
        "id": "A7",
        "question": "What happens when upsert_to_vector_db in vector_store.py falls back to local storage?",
        "expected": "answerable",
        "expected_files": ["vector_store.py"],
    },
    {
        "id": "A8",
        "question": "How does query_vector_db compute similarity when running in local offline mode?",
        "expected": "answerable",
        "expected_files": ["vector_store.py"],
    },
    {
        "id": "A9",
        "question": "How do I run the full side-by-side comparison demo from the command line?",
        "expected": "answerable",
        "expected_files": ["main.py"],
    },
    {
        "id": "A10",
        "question": "How can I run this project without real API keys or internet access?",
        "expected": "answerable",
        "expected_files": ["main.py", "config.py"],
    },
    # Not-found & off-topic questions (from docs/target_analysis.md section h)
    {
        "id": "N1",
        "question": "Where is Redis configured or connected in this repository?",
        "expected": "not found",
        "expected_files": [],
    },
    {
        "id": "N2",
        "question": "Where is the Slack webhook notification dispatched after indexing finishes?",
        "expected": "not found",
        "expected_files": [],
    },
    {
        "id": "N3",
        "question": "Where is Postgres or SQLAlchemy configured in this repository?",
        "expected": "not found",
        "expected_files": [],
    },
    {
        "id": "N4",
        "question": "Where is Celery or RabbitMQ configured for background tasks in this codebase?",
        "expected": "not found",
        "expected_files": [],
    },
    {
        "id": "N5",
        "question": "What is the current weather forecast for Tokyo today?",
        "expected": "not found",
        "expected_files": [],
    },
    {
        "id": "N6",
        "question": "Can you write me a recipe for chocolate chip cookies?",
        "expected": "not found",
        "expected_files": [],
    },
]


def run_calibration() -> list[dict]:
    settings = load_settings()
    results = []

    print(f"Starting MIN_SCORE calibration across {len(QUESTIONS)} queries (embedding + Pinecone only, no chat model)...")
    print(f"Target index: {settings.pinecone_index_name}, namespace: {settings.pinecone_namespace}\n")

    for idx, item in enumerate(QUESTIONS, 1):
        q = item["question"]
        expected = item["expected"]
        exp_files = item["expected_files"]

        print(f"[{idx}/{len(QUESTIONS)}] Querying ({expected}): {q[:60]}...")
        t0 = time.time()
        matches = search(
            question=q,
            top_k=5,
            min_score=0.0,
            settings=settings,
        )
        duration = time.time() - t0

        top1_score = matches[0]["score"] if matches else 0.0
        top3_scores = [round(m["score"], 4) for m in matches[:3]]
        top1_path = matches[0]["path"] if matches else ""
        top1_filename = Path(top1_path).name if top1_path else ""

        if expected == "answerable":
            file_match = any(Path(ef).name.lower() == top1_filename.lower() for ef in exp_files)
        else:
            file_match = "N/A"

        res_record = {
            "id": item["id"],
            "question": q,
            "expected": expected,
            "top1_score": round(top1_score, 4),
            "top3_scores": top3_scores,
            "top1_path": top1_path,
            "file_match": file_match,
            "duration": round(duration, 2),
        }
        results.append(res_record)
        time.sleep(0.5)  # gentle pacing

    return results


def write_report(results: list[dict]):
    eval_dir = PROJECT_ROOT / "eval_runs"
    eval_dir.mkdir(parents=True, exist_ok=True)
    report_file = eval_dir / "min_score_calibration.md"

    answerable = [r for r in results if r["expected"] == "answerable"]
    not_found = [r for r in results if r["expected"] == "not found"]

    ans_scores = [r["top1_score"] for r in answerable]
    nf_scores = [r["top1_score"] for r in not_found]

    min_ans = min(ans_scores) if ans_scores else 0.0
    max_ans = max(ans_scores) if ans_scores else 0.0
    min_nf = min(nf_scores) if nf_scores else 0.0
    max_nf = max(nf_scores) if nf_scores else 0.0

    lines = [
        "# MIN_SCORE Calibration Report",
        "",
        "Empirical calibration of `MIN_SCORE` using embedding + Pinecone queries only (no chat model calls).",
        f"- Target namespace: `{load_settings().pinecone_namespace}`",
        f"- Total queries: {len(results)} ({len(answerable)} answerable, {len(not_found)} not-found/off-topic)",
        "",
        "## Calibration Results Table",
        "",
        "| ID | Expected | Top-1 Score | Top-3 Scores | Top-1 File | Match Expected? | Question |",
        "| :--- | :--- | :---: | :--- | :--- | :---: | :--- |",
    ]

    for r in results:
        top3_str = ", ".join(f"{s:.4f}" for s in r["top3_scores"])
        top1_file = Path(r["top1_path"]).name if r["top1_path"] else "<none>"
        match_str = str(r["file_match"])
        lines.append(
            f"| {r['id']} | {r['expected']} | {r['top1_score']:.4f} | [{top3_str}] | `{top1_file}` | {match_str} | {r['question']} |"
        )

    lines.extend([
        "",
        "## Score Distribution Analysis",
        "",
        f"- **Answerable Questions Top-1 Range**: [{min_ans:.4f}, {max_ans:.4f}] (mean: {sum(ans_scores)/len(ans_scores):.4f})",
        f"- **Not-Found / Off-Topic Top-1 Range**: [{min_nf:.4f}, {max_nf:.4f}] (mean: {sum(nf_scores)/len(nf_scores):.4f})",
        "",
        "### Overlap Analysis",
    ])

    if max_nf >= min_ans:
        overlap_cases_ans = [r for r in answerable if r["top1_score"] <= max_nf]
        overlap_cases_nf = [r for r in not_found if r["top1_score"] >= min_ans]
        lines.append(f"- **Overlap Detected**: Yes. Not-found max score ({max_nf:.4f}) >= Answerable min score ({min_ans:.4f}).")
        lines.append(f"- Overlapping answerable questions (<= {max_nf:.4f}):")
        for r in overlap_cases_ans:
            lines.append(f"  - `{r['id']}` ({r['top1_score']:.4f}): \"{r['question']}\"")
        lines.append(f"- Overlapping not-found questions (>= {min_ans:.4f}):")
        for r in overlap_cases_nf:
            lines.append(f"  - `{r['id']}` ({r['top1_score']:.4f}): \"{r['question']}\"")
    else:
        lines.append(f"- **Clean Separation**: Yes. Clean gap between max not-found ({max_nf:.4f}) and min answerable ({min_ans:.4f}).")

    report_content = "\n".join(lines) + "\n"
    report_file.write_text(report_content, encoding="utf-8")
    print(f"\nReport written to: {report_file}")
    return report_content


if __name__ == "__main__":
    records = run_calibration()
    report = write_report(records)
    print("\n" + report)
