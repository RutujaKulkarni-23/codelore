import time
from typing import Sequence
import openai
from openai import OpenAI

from code_helper.settings import Settings, EMBED_DIMENSION


class EmbeddingError(Exception):
    """Raised when an embedding request encounters an unrecoverable failure or bad response."""
    pass


def _create_openai_client(settings: Settings) -> OpenAI:
    """Build OpenAI client configured for NVIDIA NIM."""
    return OpenAI(
        base_url=settings.nvidia_base_url,
        api_key=settings.nvidia_api_key,
        timeout=float(settings.embed_timeout_seconds),
    )


def _call_embeddings_with_retry(
    client: OpenAI,
    model: str,
    texts: list[str],
    input_type: str,
    max_retries: int = 3,
) -> list[list[float]]:
    """
    Calls NVIDIA NIM /v1/embeddings endpoint with exponential backoff on retryable errors.
    - Retries at most 3 times ONLY on 429, 5xx, and timeouts/connection errors.
    - Fails fast on 401, 403, 404 with EmbeddingError and no retries.
    - Never falls back to any other model.
    - Asserts output vectors have length EMBED_DIMENSION (2048) and count matches inputs.
    """
    if not texts:
        return []

    attempt = 0
    delay = 1.0

    while True:
        try:
            # extra_body passes input_type to NVIDIA NIM endpoint
            response = client.embeddings.create(
                model=model,
                input=texts,
                extra_body={"input_type": input_type},
            )
            data = response.data
            if len(data) != len(texts):
                raise EmbeddingError(
                    f"Mismatch in embeddings count: expected {len(texts)}, got {len(data)}"
                )

            # Sort by index to maintain exact alignment with inputs
            sorted_items = sorted(data, key=lambda x: getattr(x, "index", 0))
            vectors: list[list[float]] = []
            for item in sorted_items:
                vec = item.embedding
                if len(vec) != EMBED_DIMENSION:
                    raise EmbeddingError(
                        f"Expected embedding dimension {EMBED_DIMENSION}, got {len(vec)}"
                    )
                vectors.append(vec)

            return vectors

        except openai.AuthenticationError as e:
            # 401
            raise EmbeddingError(f"Authentication failed (401): {e}") from e
        except openai.PermissionDeniedError as e:
            # 403
            raise EmbeddingError(f"Permission denied (403): {e}") from e
        except openai.NotFoundError as e:
            # 404
            raise EmbeddingError(f"Model or endpoint not found (404): {e}") from e
        except (
            openai.RateLimitError,  # 429
            openai.InternalServerError,  # 5xx
            openai.APITimeoutError,  # timeout
            openai.APIConnectionError,  # connection error
        ) as e:
            attempt += 1
            if attempt > max_retries:
                raise EmbeddingError(
                    f"Embedding request failed after {max_retries} retries: {e}"
                ) from e
            time.sleep(delay)
            delay *= 2
        except EmbeddingError:
            raise
        except Exception as e:
            # Any unhandled client exception
            status_code = getattr(e, "status_code", None)
            if status_code in (401, 403, 404):
                raise EmbeddingError(f"Unrecoverable HTTP {status_code}: {e}") from e
            if status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                attempt += 1
                time.sleep(delay)
                delay *= 2
                continue
            raise EmbeddingError(f"Embedding request failed unexpectedly: {e}") from e


def embed_documents(
    texts: Sequence[str],
    settings: Settings,
    client: OpenAI | None = None,
) -> list[list[float]]:
    """
    Embeds multiple documents/chunks in batches of settings.embed_batch_size
    with input_type='passage'.
    """
    if not texts:
        return []

    c = client or _create_openai_client(settings)
    batch_size = max(1, settings.embed_batch_size)
    all_vectors: list[list[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = list(texts[i : i + batch_size])
        batch_vectors = _call_embeddings_with_retry(
            client=c,
            model=settings.nvidia_embed_model,
            texts=batch,
            input_type="passage",
        )
        all_vectors.extend(batch_vectors)

    return all_vectors


def embed_query(
    text: str,
    settings: Settings,
    client: OpenAI | None = None,
) -> list[float]:
    """
    Embeds a single search query with input_type='query'.
    """
    if not text or not text.strip():
        raise EmbeddingError("Cannot embed empty query text.")

    c = client or _create_openai_client(settings)
    vectors = _call_embeddings_with_retry(
        client=c,
        model=settings.nvidia_embed_model,
        texts=[text],
        input_type="query",
    )
    return vectors[0]
