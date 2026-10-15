"""
Unit tests for the strict AST citation and outline checker (scripts/verify_routing_answers.py).
Validates:
- Real bad answer (a) with no citation FAILS.
- Real bad answer (b) with sub-ranges and missing functions FAILS.
- Accurate outline answer with all 5 functions and exact AST ranges PASSES.
"""
from pathlib import Path
import pytest
from scripts.verify_routing_answers import verify_routing_answer

TARGET_DIR = Path("D:/CodeLore/targets/Naive_RAG")


def test_regression_bad_answer_a_fails_no_citations():
    """Real bad answer (a) from live run: must FAIL because it contains zero code citations."""
    bad_answer_a = (
        "The function `chunk_document` in `indexer.py` is used for chunking the document "
        "into overlapping chunks. It takes no arguments and returns the chunked document. "
        "The function is part of the indexing pipeline and is used to prepare the external "
        "knowledge into indexed vector coordinates so that relevant information can be "
        "fetched in milliseconds during live queries."
    )
    res = verify_routing_answer(
        question_id="reg_bad_a",
        question_text="Explain what chunk_document in indexer.py does",
        category="Code Explainer",
        answer_text=bad_answer_a,
        target_dir=TARGET_DIR,
    )
    assert res["passed"] is False
    assert any("no code citations" in err.lower() for err in res["errors"])


def test_regression_bad_answer_b_fails_subranges_and_missing_functions():
    """Real bad answer (b) from live run: must FAIL for sub-ranges and 4 missing functions."""
    bad_answer_b = """Verified from code:

* def calculate_cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
	+ Calculate cosine similarity between two vectors using basic math: vector_store.py:28-59
		- Calculate dot product of two vectors: vector_store.py:30-31
		- Calculate magnitude of two vectors: vector_store.py:32-33
		- Calculate cosine similarity: vector_store.py:34-35
		- Return cosine similarity: vector_store.py:36-37"""

    res = verify_routing_answer(
        question_id="reg_bad_b",
        question_text="Outline vector_store.py",
        category="Code Explainer",
        answer_text=bad_answer_b,
        target_dir=TARGET_DIR,
    )
    assert res["passed"] is False
    # Sub-ranges must fail
    sub_range_errors = [e for e in res["errors"] if "unverifiable sub-range" in e]
    assert len(sub_range_errors) == 4
    # Missing functions must fail
    assert any("missing top-level definitions in vector_store.py" in e.lower() for e in res["errors"])
    for fn_name in ["get_pinecone_client", "ensure_pinecone_index_exists", "upsert_to_vector_db", "query_vector_db"]:
        assert any(fn_name in e for e in res["errors"])


def test_correct_outline_answer_passes():
    """Correct outline answer listing all 5 functions with exact AST line ranges must PASS."""
    correct_outline = """Verified from code:
- calculate_cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float - vector_store.py:28-59
- get_pinecone_client(api_key: str) - vector_store.py:62-66
- ensure_pinecone_index_exists(client, index_name: str, dimension: int = 2048, cloud: str = 'aws', region: str = 'us-east-1') - vector_store.py:69-94
- upsert_to_vector_db(chunks_with_embeddings: list[dict], config: RAGConfig) -> int - vector_store.py:97-162
- query_vector_db(query_vector: list[float], top_k: int = 3, config: RAGConfig | None = None) -> list[dict] - vector_store.py:165-233"""

    res = verify_routing_answer(
        question_id="test_correct",
        question_text="Outline vector_store.py",
        category="Code Explainer",
        answer_text=correct_outline,
        target_dir=TARGET_DIR,
    )
    assert res["passed"] is True
    assert len(res["errors"]) == 0
    assert len(res["valid_citations"]) == 5
    assert len(res["invalid_citations"]) == 0
