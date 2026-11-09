"""ChromaDB persistence for the active-document chunk corpus.

Only active document revisions are written to this collection. Archived
revisions live in the Stage 2 JSON output and are deliberately never indexed
for chat retrieval.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import chromadb

from backend.core.config import settings

logger = logging.getLogger(__name__)


class VectorStoreError(RuntimeError):
    """Raised when the local vector store cannot be used."""


@dataclass(slots=True)
class ChunkRecord:
    """A chunk ready to be stored, with its embedding and metadata."""

    chunk_id: str
    chunk_text: str
    embedding: list[float]
    metadata: dict[str, str | int | float | bool]


@dataclass(slots=True)
class RetrievedChunk:
    """A chunk returned by similarity search, with full source identity."""

    chunk_id: str
    text: str
    document_id: str
    document_title: str
    document_code: str
    revision: str
    document_status: str
    source_filename: str
    page_number: int
    similarity: float


@dataclass(slots=True)
class VectorStore:
    """Local persistent ChromaDB collection of active document chunks."""

    persist_directory: Path | None = None
    collection_name: str | None = None
    _client: Any = field(default=None, init=False, repr=False)
    _collection: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.persist_directory = Path(
            self.persist_directory or settings.chroma_persist_directory
        )
        self.collection_name = (
            self.collection_name or settings.chroma_active_collection
        )

    # --- infrastructure ---

    def _get_collection(self) -> Any:
        if self._collection is not None:
            return self._collection
        try:
            self.persist_directory.mkdir(parents=True, exist_ok=True)
            if self._client is None:
                self._client = chromadb.PersistentClient(
                    path=str(self.persist_directory)
                )
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=None,
                # Cosine distance maps cleanly to a 0-1 similarity score.
                configuration={"hnsw": {"space": "cosine"}},
            )
            return self._collection
        except Exception as exc:  # noqa: BLE001 - surfaced as a domain error
            logger.error("ChromaDB unavailable: %s", type(exc).__name__)
            raise VectorStoreError(
                "The local vector database could not be opened. Check the "
                "CHROMA_PERSIST_DIRECTORY setting and file permissions."
            ) from exc

    # --- writes ---

    def existing_content_hashes(self) -> dict[str, str]:
        """Map stored chunk id -> stored content hash (for skip-on-unchanged)."""
        collection = self._get_collection()
        try:
            result = collection.get(include=["metadatas"])
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError("Could not read the existing index") from exc

        hashes: dict[str, str] = {}
        ids = result.get("ids") or []
        metadatas = result.get("metadatas") or []
        for chunk_id, metadata in zip(ids, metadatas):
            content_hash = (metadata or {}).get("content_hash")
            if content_hash:
                hashes[chunk_id] = str(content_hash)
        return hashes

    def upsert(self, records: Sequence[ChunkRecord]) -> None:
        """Insert or update records; chunk ids make the operation idempotent."""
        if not records:
            return
        try:
            self._get_collection().upsert(
                ids=[record.chunk_id for record in records],
                embeddings=[record.embedding for record in records],
                documents=[record.chunk_text for record in records],
                metadatas=[record.metadata for record in records],
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("ChromaDB upsert failed: %s", type(exc).__name__)
            raise VectorStoreError("Failed to write chunks to the vector store") from exc

    def delete(self, chunk_ids: Sequence[str]) -> None:
        """Delete chunk ids that are no longer part of the corpus."""
        if not chunk_ids:
            return
        try:
            self._get_collection().delete(ids=list(chunk_ids))
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError("Failed to remove stale chunks") from exc

    # --- reads ---

    def count(self) -> int:
        try:
            return int(self._get_collection().count())
        except VectorStoreError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreError("Could not count indexed chunks") from exc

    def query(
        self,
        embedding: Sequence[float],
        *,
        top_k: int | None = None,
        where: Mapping[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        """Return the ``top_k`` most similar chunks with their metadata."""
        limit = max(1, top_k or settings.retrieval_top_k)
        try:
            result = self._get_collection().query(
                query_embeddings=[list(embedding)],
                n_results=limit,
                where=dict(where) if where else None,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("ChromaDB query failed: %s", type(exc).__name__)
            raise VectorStoreError("Vector search failed") from exc

        return _chunks_from_query(result)


def _chunks_from_query(result: Mapping[str, Any]) -> list[RetrievedChunk]:
    """Flatten a ChromaDB query result into ``RetrievedChunk`` objects."""
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    ids = (result.get("ids") or [[]])[0]

    chunks: list[RetrievedChunk] = []
    for index, chunk_id in enumerate(ids):
        metadata = metadatas[index] or {}
        distance = float(distances[index]) if index < len(distances) else 1.0
        chunks.append(
            RetrievedChunk(
                chunk_id=str(chunk_id),
                text=documents[index] or "",
                document_id=str(metadata.get("document_id", "")),
                document_title=str(metadata.get("document_title", "")),
                document_code=str(metadata.get("document_code", "")),
                revision=str(metadata.get("revision", "")),
                document_status=str(metadata.get("document_status", "")),
                source_filename=str(metadata.get("source_filename", "")),
                page_number=int(metadata.get("page_number", 0)),
                # Cosine distance -> similarity, clamped to a sane range.
                similarity=max(0.0, min(1.0, 1.0 - distance)),
            )
        )
    return chunks
