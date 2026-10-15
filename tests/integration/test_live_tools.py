import os
import pytest
from code_helper.tools.search_tools import rag_search


@pytest.mark.live
def test_live_rag_search_tool():
    if os.getenv("RUN_LIVE") != "1":
        pytest.skip("Skipping live rag_search tool test because RUN_LIVE is not set to 1")

    res = rag_search("Where is the Pinecone index created?", top_k=3)
    assert not res.startswith("ERROR:")
    assert not res.startswith("NOT FOUND:")
    assert "vector_store.py" in res
    assert "ensure_pinecone_index_exists" in res
