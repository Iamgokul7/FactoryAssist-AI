"""Gemini embedding generation.

Documents and queries are embedded with the model from ``.env``. Both paths use
the SDK's task-type hint (``RETRIEVAL_DOCUMENT`` / ``RETRIEVAL_QUERY``), which
Google recommends when the vectors are used for retrieval.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence

from google import genai
from google.genai import types

from backend.core.config import settings
from backend.services.gemini_client import (
    GeminiNotConfiguredError,
    GeminiRequestError,
    create_client,
    describe_error,
    is_retryable,
)

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = 2.0


class EmbeddingError(GeminiRequestError):
    """Raised when chunk or query embeddings cannot be produced."""


class EmbeddingService:
    """Thin wrapper around the Gemini embedding endpoint."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        batch_size: int | None = None,
        dimensions: int | None = None,
    ) -> None:
        self._api_key = api_key
        self.model = model or settings.gemini_embedding_model
        self.batch_size = max(1, batch_size or settings.embedding_batch_size)
        self.dimensions = (
            dimensions if dimensions is not None else settings.embedding_dimensions
        )
        self._client: genai.Client | None = None

    @property
    def is_configured(self) -> bool:
        return bool((self._api_key or settings.gemini_api_key).strip())

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed chunk texts for storage."""
        return self._embed(texts, task_type="RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> list[float]:
        """Embed a single supervisor question."""
        vectors = self._embed([text], task_type="RETRIEVAL_QUERY")
        return vectors[0]

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = create_client(self._api_key)
        return self._client

    def _embed(self, texts: Sequence[str], *, task_type: str) -> list[list[float]]:
        cleaned = [text.strip() for text in texts]
        if not cleaned or any(not text for text in cleaned):
            raise EmbeddingError("Refusing to embed empty text")
        if not self.is_configured:
            raise GeminiNotConfiguredError(
                "GEMINI_API_KEY is not configured. Add it to the .env file in the "
                "project root."
            )

        vectors: list[list[float]] = []
        for start in range(0, len(cleaned), self.batch_size):
            batch = cleaned[start : start + self.batch_size]
            vectors.extend(self._embed_batch(batch, task_type=task_type))
        return vectors

    def _embed_batch(self, batch: list[str], *, task_type: str) -> list[list[float]]:
        config = types.EmbedContentConfig(task_type=task_type)
        if self.dimensions:
            config.output_dimensionality = self.dimensions

        last_error: Exception | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = self._get_client().models.embed_content(
                    model=self.model, contents=batch, config=config
                )
                return _vectors_from_response(response, expected=len(batch))
            except (GeminiNotConfiguredError, EmbeddingError):
                raise
            except Exception as exc:  # noqa: BLE001 - normalised below
                last_error = exc
                if attempt == _MAX_ATTEMPTS or not is_retryable(exc):
                    break
                delay = _BACKOFF_SECONDS * attempt
                logger.warning(
                    "Embedding request failed (attempt %s/%s), retrying in %.0fs",
                    attempt,
                    _MAX_ATTEMPTS,
                    delay,
                )
                time.sleep(delay)

        message = describe_error(last_error) if last_error else "Embedding failed"
        logger.error("Embedding request failed: %s", type(last_error).__name__)
        raise EmbeddingError(message) from last_error


def _vectors_from_response(response: object, *, expected: int) -> list[list[float]]:
    """Extract and validate embedding vectors from an SDK response."""
    embeddings = getattr(response, "embeddings", None) or []
    vectors = [list(embedding.values or []) for embedding in embeddings]

    if len(vectors) != expected:
        raise EmbeddingError(
            f"Embedding response contained {len(vectors)} vectors for {expected} inputs"
        )
    if any(not vector for vector in vectors):
        raise EmbeddingError("Embedding response contained an empty vector")
    return vectors
