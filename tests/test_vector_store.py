from unittest.mock import MagicMock
from pathlib import Path
import pytest
from code_helper.settings import Settings
from code_helper.rag.chunker import Chunk
from code_helper.rag.vector_store import (
    get_index,
    upsert_chunks,
    query,
    wait_until_count,
    VectorStoreError,
    _truncate_utf8,
)


@pytest.fixture
def dummy_settings(tmp_path: Path) -> Settings:
    fake_nv = "".join(["nvapi-", "mock", "1234567890"])
    fake_pc = "".join(["pc-", "mock", "1234567890"])
    return Settings(
        nvidia_api_key=fake_nv,
        nvidia_nim_api_key=fake_nv,
        nvidia_base_url="https://mock.nvidia.com/v1",
        nvidia_chat_model="nvidia/mock-chat",
        nvidia_embed_model="nvidia/nemotron-3-embed-1b",
        pinecone_api_key=fake_pc,
        pinecone_index_name="code-helper",
        pinecone_cloud="aws",
        pinecone_region="us-east-1",
        pinecone_namespace="test-ns",
        target_project_path=tmp_path,
        top_k=5,
        min_score=0.0,
        pythonutf8="1",
        metadata_text_max_bytes=50,
    )


def test_truncate_utf8():
    short_text = "Hello world"
    res, truncated = _truncate_utf8(short_text, 50)
    assert res == short_text
    assert not truncated

    long_text = "a" * 100
    res, truncated = _truncate_utf8(long_text, 50)
    assert len(res.encode("utf-8")) <= 50
    assert truncated


def test_get_index_refuses_when_missing_and_allow_create_false(dummy_settings: Settings):
    mock_pc = MagicMock()
    mock_pc.list_indexes.return_value = []

    with pytest.raises(VectorStoreError, match="does not exist and allow_create is False"):
        get_index(settings=dummy_settings, client=mock_pc, allow_create=False)


def test_get_index_creates_index_when_missing_and_allowed(dummy_settings: Settings):
    mock_pc = MagicMock()
    # First list_indexes has no code-helper
    mock_pc.list_indexes.return_value = []
    # describe_index returns valid 2048 cosine
    desc = MagicMock()
    desc.dimension = 2048
    desc.metric = "cosine"
    mock_pc.describe_index.return_value = desc

    idx = get_index(settings=dummy_settings, client=mock_pc, allow_create=True)
    assert mock_pc.create_index.call_count == 1
    mock_pc.Index.assert_called_once_with("code-helper")


def test_get_index_refuses_wrong_dimension(dummy_settings: Settings):
    mock_pc = MagicMock()
    existing_idx = MagicMock()
    existing_idx.name = "code-helper"
    mock_pc.list_indexes.return_value = [existing_idx]

    desc = MagicMock()
    desc.dimension = 1536  # wrong dimension
    desc.metric = "cosine"
    mock_pc.describe_index.return_value = desc

    with pytest.raises(VectorStoreError, match="dimension mismatch: expected 2048, got 1536"):
        get_index(settings=dummy_settings, client=mock_pc, allow_create=False)


def test_get_index_refuses_wrong_metric(dummy_settings: Settings):
    mock_pc = MagicMock()
    existing_idx = MagicMock()
    existing_idx.name = "code-helper"
    mock_pc.list_indexes.return_value = [existing_idx]

    desc = MagicMock()
    desc.dimension = 2048
    desc.metric = "euclidean"  # wrong metric
    mock_pc.describe_index.return_value = desc

    with pytest.raises(VectorStoreError, match="metric mismatch: expected 'cosine', got 'euclidean'"):
        get_index(settings=dummy_settings, client=mock_pc, allow_create=False)


def test_upsert_chunks_truncates_metadata_and_batches(dummy_settings: Settings):
    mock_index = MagicMock()
    chunks = [
        Chunk(
            id="c1",
            path="file1.py",
            symbol="foo",
            kind="function",
            start_line=1,
            end_line=5,
            text="short text",
            content_hash="h1",
            chunk_config_id="cfg1",
        ),
        Chunk(
            id="c2",
            path="file2.py",
            symbol="bar",
            kind="class",
            start_line=10,
            end_line=50,
            text="x" * 200,  # exceeds dummy_settings.metadata_text_max_bytes (50)
            content_hash="h2",
            chunk_config_id="cfg1",
        ),
    ]
    vecs = [[0.1] * 2048, [0.2] * 2048]

    count = upsert_chunks(
        index=mock_index,
        chunks=chunks,
        vectors=vecs,
        namespace="test-ns",
        settings=dummy_settings,
        batch_size=10,
    )
    assert count == 2
    assert mock_index.upsert.call_count == 1
    call_kwargs = mock_index.upsert.call_args.kwargs
    assert call_kwargs["namespace"] == "test-ns"
    upserted_records = call_kwargs["vectors"]
    assert len(upserted_records) == 2
    # Verify metadata fields
    assert upserted_records[0]["metadata"]["truncated"] is False
    assert upserted_records[1]["metadata"]["truncated"] is True
    assert len(upserted_records[1]["metadata"]["text"].encode("utf-8")) <= 50


def test_query_filters_by_min_score(dummy_settings: Settings):
    mock_index = MagicMock()
    res = MagicMock()
    m1 = MagicMock()
    m1.id = "c1"
    m1.score = 0.85
    m1.metadata = {"path": "a.py", "symbol": "foo", "start_line": 1, "end_line": 10, "text": "code"}
    m2 = MagicMock()
    m2.score = 0.45
    m2.metadata = {"path": "b.py", "symbol": "bar", "start_line": 5, "end_line": 15, "text": "more code"}
    res.matches = [m1, m2]
    mock_index.query.return_value = res

    results = query(
        index=mock_index,
        vector=[0.1] * 2048,
        top_k=2,
        namespace="test-ns",
        min_score=0.5,
    )
    # Only m1 has score >= 0.5
    assert len(results) == 1
    assert results[0]["id"] == "c1"
    assert results[0]["score"] == 0.85


def test_wait_until_count_timeout(monkeypatch):
    import time
    monkeypatch.setattr(time, "sleep", lambda s: None)

    mock_index = MagicMock()
    stats = MagicMock()
    stats.namespaces = {"test-ns": {"vector_count": 5}}
    mock_index.describe_index_stats.return_value = stats

    # Waiting for 10 vectors when only 5 exist
    synced = wait_until_count(
        index=mock_index,
        namespace="test-ns",
        expected_count=10,
        timeout=0.01,
        poll_interval=0.001,
    )
    assert not synced
