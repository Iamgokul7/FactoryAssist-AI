"""Builds the local ChromaDB index from the processed active chunks.

Run once after the document pipeline:

    python -m backend.services.ingestion_service

Only ``active_chunks.json`` is read, so superseded revisions can never reach
the active collection. Re-running is safe: unchanged chunks are skipped and
changed ones are updated in place.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from backend.core.config import settings
from backend.services.embedding_service import EmbeddingError, EmbeddingService
from backend.services.gemini_client import GeminiNotConfiguredError
from backend.services.knowledge_base import active_revisions
from backend.services.vector_store import ChunkRecord, VectorStore, VectorStoreError

logger = logging.getLogger(__name__)

REQUIRED_CHUNK_FIELDS = (
    "chunk_id",
    "document_id",
    "document_title",
    "document_code",
    "revision",
    "document_status",
    "source_filename",
    "page_number",
    "chunk_text",
)


class IngestionError(RuntimeError):
    """Raised when ingestion cannot proceed."""


@dataclass(slots=True)
class IngestionReport:
    """Outcome of one ingestion run."""

    chunks_read: int = 0
    chunks_valid: int = 0
    chunks_embedded: int = 0
    chunks_skipped_unchanged: int = 0
    chunks_failed: int = 0
    stale_records_removed: int = 0
    collection: str = ""
    indexed_total: int = 0
    embedding_model: str = ""
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def read_active_chunks(
    path: Path | None = None,
) -> list[dict[str, Any]]:
    """Load the processed active chunks produced in Stage 2."""
    chunks_path = path or settings.processed_data_directory / "active_chunks.json"
    if not chunks_path.is_file():
        raise IngestionError(
            "Processed chunks not found at "
            f"{chunks_path}. Run 'python -m backend.services.document_pipeline' first."
        )
    try:
        with chunks_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise IngestionError(f"Could not read processed chunks: {exc}") from exc
    if not isinstance(data, list):
        raise IngestionError("Processed chunks file is not a JSON array")
    return [chunk for chunk in data if isinstance(chunk, dict)]


def validate_chunks(
    chunks: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Keep only well-formed, active chunks that pass revision checks."""
    revisions = active_revisions()
    valid: list[dict[str, Any]] = []
    errors: list[str] = []

    for position, chunk in enumerate(chunks, start=1):
        chunk_id = str(chunk.get("chunk_id") or f"index-{position}")
        missing = [f for f in REQUIRED_CHUNK_FIELDS if chunk.get(f) in (None, "")]
        if missing:
            errors.append(f"{chunk_id}: missing fields {', '.join(missing)}")
            continue
        if not str(chunk["chunk_text"]).strip():
            errors.append(f"{chunk_id}: empty chunk text")
            continue
        if chunk["document_status"] != "active":
            errors.append(
                f"{chunk_id}: status '{chunk['document_status']}' is not active"
            )
            continue

        expected_document_id = revisions.get(str(chunk["document_code"]))
        if expected_document_id and expected_document_id != str(chunk["document_id"]):
            errors.append(
                f"{chunk_id}: revision {chunk['revision']} of "
                f"{chunk['document_code']} is not the active revision "
                f"({expected_document_id})"
            )
            continue

        try:
            int(chunk["page_number"])
        except (TypeError, ValueError):
            errors.append(f"{chunk_id}: invalid page_number")
            continue

        valid.append(chunk)

    return valid, errors


def ingest_active_chunks() -> IngestionReport:
    """Embed and store every active chunk that is new or changed."""
    report = IngestionReport(
        collection=settings.chroma_active_collection,
        embedding_model=settings.gemini_embedding_model,
    )

    raw_chunks = read_active_chunks()
    report.chunks_read = len(raw_chunks)

    valid_chunks, validation_errors = validate_chunks(raw_chunks)
    report.chunks_valid = len(valid_chunks)
    report.errors.extend(validation_errors)

    store = VectorStore()
    embedding_service = EmbeddingService()

    if not embedding_service.is_configured:
        raise GeminiNotConfiguredError(
            "GEMINI_API_KEY is not configured. Add it to the .env file in the "
            "project root, then re-run ingestion."
        )

    existing = store.existing_content_hashes()
    pending: list[tuple[dict[str, Any], str]] = []

    for chunk in valid_chunks:
        content_hash = _content_hash(str(chunk["chunk_text"]))
        chunk_id = str(chunk["chunk_id"])
        if existing.get(chunk_id) == content_hash:
            report.chunks_skipped_unchanged += 1
            continue
        pending.append((chunk, content_hash))

    logger.info(
        "Embedding %s new/changed chunks (%s unchanged, %s invalid)",
        len(pending),
        report.chunks_skipped_unchanged,
        len(validation_errors),
    )

    if pending:
        texts = [str(chunk["chunk_text"]) for chunk, _ in pending]
        try:
            vectors = embedding_service.embed_documents(texts)
        except (GeminiNotConfiguredError, EmbeddingError) as exc:
            report.chunks_failed = len(pending)
            report.errors.append(str(exc))
            raise

        records = [
            ChunkRecord(
                chunk_id=str(chunk["chunk_id"]),
                chunk_text=str(chunk["chunk_text"]),
                embedding=vector,
                metadata=_metadata_for(chunk, content_hash),
            )
            for (chunk, content_hash), vector in zip(pending, vectors)
        ]
        store.upsert(records)
        report.chunks_embedded = len(records)

    current_ids = {str(chunk["chunk_id"]) for chunk in valid_chunks}
    # Chunks uploaded through the management interface are governed by the
    # activation/archival workflow, so this baseline cleanup must not delete
    # them just because they are not in active_chunks.json.
    managed_ids = store.managed_chunk_ids()
    stale_ids = [
        chunk_id
        for chunk_id in existing
        if chunk_id not in current_ids and chunk_id not in managed_ids
    ]
    if stale_ids:
        store.delete(stale_ids)
        report.stale_records_removed = len(stale_ids)
        logger.info("Removed %s stale chunk(s) from the index", len(stale_ids))

    report.indexed_total = store.count()
    return report


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _metadata_for(
    chunk: dict[str, Any], content_hash: str
) -> dict[str, str | int | float | bool]:
    """ChromaDB metadata: flat scalar values only."""
    return {
        "document_id": str(chunk["document_id"]),
        "document_title": str(chunk["document_title"]),
        "document_code": str(chunk["document_code"]),
        "revision": str(chunk["revision"]),
        "document_status": str(chunk["document_status"]),
        "source_filename": str(chunk["source_filename"]),
        "page_number": int(chunk["page_number"]),
        "page_range": str(chunk.get("page_range") or chunk["page_number"]),
        "chunk_index": int(chunk.get("chunk_index") or 0),
        "content_hash": content_hash,
    }


def main() -> int:
    """CLI entry point: ingest and print a report."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    try:
        report = ingest_active_chunks()
    except GeminiNotConfiguredError as exc:
        print(f"Configuration error: {exc}")
        return 2
    except (IngestionError, VectorStoreError, EmbeddingError) as exc:
        print(f"Ingestion failed: {exc}")
        return 1

    print(json.dumps(report.as_dict(), indent=2, ensure_ascii=False))
    return 0 if not report.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
