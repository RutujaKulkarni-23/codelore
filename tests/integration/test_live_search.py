import os
import pytest
from code_helper.rag.search import search
from code_helper.settings import load_settings


@pytest.mark.live
def test_live_search_query():
    if os.getenv("RUN_LIVE") != "1":
        pytest.skip("Skipping live integration test because RUN_LIVE is not set to 1")

    settings = load_settings()
    results = search("Where is the Pinecone index created?", top_k=3, settings=settings)
    assert len(results) > 0
    first = results[0]
    assert "path" in first
    assert "start_line" in first
    assert "end_line" in first
    assert "score" in first
    assert "text" in first
    assert first["score"] > 0.0
