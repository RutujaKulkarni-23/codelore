from unittest.mock import MagicMock
from pathlib import Path
import pytest
import openai
from code_helper.settings import Settings
from code_helper.rag.embedder import embed_documents, embed_query, EmbeddingError


@pytest.fixture
def dummy_settings(tmp_path: Path) -> Settings:
    # Build fake key at runtime without real-looking literals
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
        embed_batch_size=2,
    )


def test_embed_documents_batches_and_validates_dimension(dummy_settings: Settings):
    mock_client = MagicMock()
    # Batch size is 2, so 3 texts -> 2 batches
    dummy_vec = [0.1] * 2048

    def fake_create(model, input, extra_body):
        assert extra_body.get("input_type") == "passage"
        resp = MagicMock()
        items = []
        for idx, text in enumerate(input):
            item = MagicMock()
            item.index = idx
            item.embedding = dummy_vec
            items.append(item)
        resp.data = items
        return resp

    mock_client.embeddings.create.side_effect = fake_create

    vectors = embed_documents(["text1", "text2", "text3"], settings=dummy_settings, client=mock_client)
    assert len(vectors) == 3
    assert len(vectors[0]) == 2048
    assert mock_client.embeddings.create.call_count == 2


def test_embed_query_passes_query_input_type(dummy_settings: Settings):
    mock_client = MagicMock()
    dummy_vec = [0.2] * 2048

    def fake_create(model, input, extra_body):
        assert extra_body.get("input_type") == "query"
        resp = MagicMock()
        item = MagicMock()
        item.index = 0
        item.embedding = dummy_vec
        resp.data = [item]
        return resp

    mock_client.embeddings.create.side_effect = fake_create

    vec = embed_query("What is the function?", settings=dummy_settings, client=mock_client)
    assert len(vec) == 2048
    assert mock_client.embeddings.create.call_count == 1


def test_embed_rejects_empty_query(dummy_settings: Settings):
    mock_client = MagicMock()
    with pytest.raises(EmbeddingError, match="empty query text"):
        embed_query("   ", settings=dummy_settings, client=mock_client)


def test_embed_rejects_wrong_vector_length(dummy_settings: Settings):
    mock_client = MagicMock()
    # Return vector of length 512 instead of 2048
    def fake_create(model, input, extra_body):
        resp = MagicMock()
        item = MagicMock()
        item.index = 0
        item.embedding = [0.1] * 512
        resp.data = [item]
        return resp

    mock_client.embeddings.create.side_effect = fake_create

    with pytest.raises(EmbeddingError, match="Expected embedding dimension 2048"):
        embed_query("test query", settings=dummy_settings, client=mock_client)


def test_embed_fails_fast_on_401_403_404(dummy_settings: Settings):
    mock_client = MagicMock()
    req = MagicMock()

    # 401
    mock_client.embeddings.create.side_effect = openai.AuthenticationError("Invalid API key", response=MagicMock(status_code=401), body=None)
    with pytest.raises(EmbeddingError, match="Authentication failed \\(401\\)"):
        embed_query("hello", settings=dummy_settings, client=mock_client)
    assert mock_client.embeddings.create.call_count == 1

    # 403
    mock_client.embeddings.create.reset_mock()
    mock_client.embeddings.create.side_effect = openai.PermissionDeniedError("Forbidden", response=MagicMock(status_code=403), body=None)
    with pytest.raises(EmbeddingError, match="Permission denied \\(403\\)"):
        embed_query("hello", settings=dummy_settings, client=mock_client)
    assert mock_client.embeddings.create.call_count == 1

    # 404
    mock_client.embeddings.create.reset_mock()
    mock_client.embeddings.create.side_effect = openai.NotFoundError("Model not found", response=MagicMock(status_code=404), body=None)
    with pytest.raises(EmbeddingError, match="not found \\(404\\)"):
        embed_query("hello", settings=dummy_settings, client=mock_client)
    assert mock_client.embeddings.create.call_count == 1


def test_embed_retries_on_rate_limit_and_server_error(dummy_settings: Settings, monkeypatch):
    import time
    monkeypatch.setattr(time, "sleep", lambda s: None)

    mock_client = MagicMock()
    # 429 then 500 then success
    dummy_vec = [0.5] * 2048
    resp_success = MagicMock()
    item = MagicMock()
    item.index = 0
    item.embedding = dummy_vec
    resp_success.data = [item]

    mock_client.embeddings.create.side_effect = [
        openai.RateLimitError("Rate limit", response=MagicMock(status_code=429), body=None),
        openai.InternalServerError("Server error", response=MagicMock(status_code=500), body=None),
        resp_success,
    ]

    vec = embed_query("hello retry", settings=dummy_settings, client=mock_client)
    assert len(vec) == 2048
    assert mock_client.embeddings.create.call_count == 3


def test_embed_exhausts_retries_and_raises(dummy_settings: Settings, monkeypatch):
    import time
    monkeypatch.setattr(time, "sleep", lambda s: None)

    mock_client = MagicMock()
    mock_client.embeddings.create.side_effect = openai.RateLimitError(
        "Rate limit", response=MagicMock(status_code=429), body=None
    )

    with pytest.raises(EmbeddingError, match="failed after 3 retries"):
        embed_query("hello fail", settings=dummy_settings, client=mock_client)
    # Initial try + 3 retries = 4 calls
    assert mock_client.embeddings.create.call_count == 4
