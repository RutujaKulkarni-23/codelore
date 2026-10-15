import time
from typing import Any, Sequence
from pinecone import Pinecone, ServerlessSpec
from pinecone.index import Index

from code_helper.rag.chunker import Chunk
from code_helper.settings import Settings, EMBED_DIMENSION, PINECONE_METRIC


class VectorStoreError(Exception):
    """Raised when vector store operations fail or configuration is mismatched."""
    pass


def _truncate_utf8(text: str, max_bytes: int) -> tuple[str, bool]:
    """Truncates text to at most max_bytes without slicing multi-byte characters."""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text, False
    truncated_bytes = encoded[:max_bytes]
    # decode with ignore to avoid broken UTF-8 boundary
    safe_text = truncated_bytes.decode("utf-8", errors="ignore")
    return safe_text, True


def get_pinecone_client(settings: Settings) -> Pinecone:
    """Instantiate Pinecone client."""
    return Pinecone(api_key=settings.pinecone_api_key)


def get_index(
    settings: Settings,
    client: Pinecone | None = None,
    allow_create: bool = False,
) -> Index:
    """
    Retrieves Index handle for settings.pinecone_index_name.
    - If missing and allow_create=True, creates index with ServerlessSpec(cloud, region),
      dimension 2048, metric 'cosine'.
    - If missing and allow_create=False, raises VectorStoreError.
    - If already exists, DESCRIBES it and REFUSES if dimension != 2048 or metric != 'cosine'.
    - Never modifies or deletes an existing index.
    """
    pc = client or get_pinecone_client(settings)
    index_name = settings.pinecone_index_name

    existing_indexes = pc.list_indexes()
    names = [idx.name for idx in existing_indexes]

    if index_name not in names:
        if not allow_create:
            raise VectorStoreError(
                f"Pinecone index '{index_name}' does not exist and allow_create is False."
            )
        # Create serverless index
        pc.create_index(
            name=index_name,
            dimension=EMBED_DIMENSION,
            metric=PINECONE_METRIC,
            spec=ServerlessSpec(
                cloud=settings.pinecone_cloud,
                region=settings.pinecone_region,
            ),
        )

    # Describe index and validate properties
    desc = pc.describe_index(index_name)
    desc_dim = getattr(desc, "dimension", None)
    desc_metric = getattr(desc, "metric", None)

    if desc_dim != EMBED_DIMENSION:
        raise VectorStoreError(
            f"Index '{index_name}' dimension mismatch: expected {EMBED_DIMENSION}, got {desc_dim}"
        )
    if str(desc_metric).lower() != PINECONE_METRIC.lower():
        raise VectorStoreError(
            f"Index '{index_name}' metric mismatch: expected '{PINECONE_METRIC}', got '{desc_metric}'"
        )

    return pc.Index(index_name)


def upsert_chunks(
    index: Index,
    chunks: Sequence[Chunk],
    vectors: Sequence[Sequence[float]],
    namespace: str,
    settings: Settings,
    batch_size: int = 100,
) -> int:
    """
    Upserts chunks and their embedding vectors into the specified namespace.
    Batches records in slices within Pinecone limits (max 1000).
    Builds metadata per chunk:
      path, symbol, kind, start_line, end_line, chunk_config_id, embed_model, content_hash,
      text (UTF-8 truncated to METADATA_TEXT_MAX_BYTES with 'truncated' boolean flag).
    Returns count of upserted vectors.
    """
    if len(chunks) != len(vectors):
        raise VectorStoreError(
            f"Mismatch between chunks ({len(chunks)}) and vectors ({len(vectors)}) count."
        )
    if not chunks:
        return 0

    max_batch = min(1000, batch_size)
    total_upserted = 0

    records: list[dict[str, Any]] = []
    for chunk, vec in zip(chunks, vectors):
        safe_text, is_truncated = _truncate_utf8(chunk.text, settings.metadata_text_max_bytes)
        meta = {
            "path": chunk.path,
            "symbol": chunk.symbol,
            "kind": chunk.kind,
            "start_line": int(chunk.start_line),
            "end_line": int(chunk.end_line),
            "chunk_config_id": chunk.chunk_config_id,
            "embed_model": settings.nvidia_embed_model,
            "content_hash": chunk.content_hash,
            "text": safe_text,
            "truncated": is_truncated,
        }
        records.append({
            "id": chunk.id,
            "values": list(vec),
            "metadata": meta,
        })

    for i in range(0, len(records), max_batch):
        batch = records[i : i + max_batch]
        index.upsert(vectors=batch, namespace=namespace)
        total_upserted += len(batch)

    return total_upserted


def query(
    index: Index,
    vector: Sequence[float],
    top_k: int,
    namespace: str,
    min_score: float = 0.0,
) -> list[dict[str, Any]]:
    """
    Queries Pinecone index with the given vector.
    Returns matches with score >= min_score, containing metadata.
    """
    if len(vector) != EMBED_DIMENSION:
        raise VectorStoreError(
            f"Query vector dimension must be {EMBED_DIMENSION}, got {len(vector)}"
        )

    res = index.query(
        vector=list(vector),
        top_k=top_k,
        namespace=namespace,
        include_metadata=True,
    )

    matches = []
    for m in getattr(res, "matches", []):
        score = float(getattr(m, "score", 0.0))
        if score >= min_score:
            meta = getattr(m, "metadata", {}) or {}
            matches.append({
                "id": getattr(m, "id", ""),
                "score": score,
                "path": meta.get("path", ""),
                "symbol": meta.get("symbol", ""),
                "kind": meta.get("kind", ""),
                "start_line": meta.get("start_line", 0),
                "end_line": meta.get("end_line", 0),
                "text": meta.get("text", ""),
                "truncated": meta.get("truncated", False),
            })

    return matches


def wait_until_count(
    index: Index,
    namespace: str,
    expected_count: int,
    timeout: float = 30.0,
    poll_interval: float = 1.0,
) -> bool:
    """
    Polls index.describe_index_stats() until the vector count in namespace
    equals or exceeds expected_count, or until timeout passes.
    Returns True if expected count is reached, False otherwise.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        stats = index.describe_index_stats()
        ns_stats = getattr(stats, "namespaces", {}) or {}
        # ns_stats can be dict-like or object
        count = 0
        if isinstance(ns_stats, dict) and namespace in ns_stats:
            ns_info = ns_stats[namespace]
            count = getattr(ns_info, "vector_count", None) or (
                ns_info.get("vector_count", 0) if isinstance(ns_info, dict) else 0
            )
        elif hasattr(ns_stats, get := "get"):
            ns_info = ns_stats.get(namespace)
            if ns_info:
                count = getattr(ns_info, "vector_count", 0)

        if count >= expected_count:
            return True
        time.sleep(poll_interval)

    return False
