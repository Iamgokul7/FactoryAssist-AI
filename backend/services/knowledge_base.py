"""Read-only access to the document corpus metadata.

Two sources are combined here:

* the Stage 2 manifest, which describes the original curated documents;
* the management store, which describes documents uploaded and approved
  through the management interface.

Keeping the merge in one place means the dashboard, the status endpoint and the
retrieval service all agree on which revision of each document is active.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from backend.core.config import settings
from backend.services import management_store

logger = logging.getLogger(__name__)

MANIFEST_FILENAME = "document_manifest.json"
_DOCUMENT_FIELDS = (
    "document_id",
    "document_code",
    "document_title",
    "document_type",
    "revision",
    "effective_date",
    "document_status",
    "page_count",
    "chunk_count",
    "source_filename",
    "supersedes_document_id",
    "superseded_by_document_id",
)


def manifest_path() -> Path:
    return settings.processed_data_directory / MANIFEST_FILENAME


def load_manifest() -> dict[str, Any] | None:
    """Return the parsed manifest, or ``None`` when it has not been generated."""
    path = manifest_path()
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Could not read the document manifest: %s", type(exc).__name__)
        return None
    return data if isinstance(data, dict) else None


def _manifest_documents() -> list[dict[str, Any]]:
    manifest = load_manifest() or {}
    raw = manifest.get("documents")
    if not isinstance(raw, list):
        return []
    return [
        {field: document.get(field) for field in _DOCUMENT_FIELDS}
        for document in raw
        if isinstance(document, dict)
    ]


def _managed_documents() -> list[dict[str, Any]]:
    """Uploaded revisions, projected onto the manifest's field names."""
    try:
        records = management_store.get_document_store().all()
    except Exception as exc:  # noqa: BLE001 - corpus views must still render
        logger.error("Managed document records unavailable: %s", type(exc).__name__)
        return []

    projected: list[dict[str, Any]] = []
    for record in records:
        projected.append(
            {
                "document_id": record.get("document_key"),
                "document_code": record.get("document_code"),
                "document_title": record.get("document_title"),
                "document_type": record.get("category"),
                "revision": record.get("revision"),
                "effective_date": record.get("effective_date"),
                "document_status": record.get("status"),
                "page_count": record.get("page_count"),
                "chunk_count": record.get("chunk_count"),
                "source_filename": record.get("source_filename"),
                "supersedes_document_id": record.get("supersedes_document_key"),
                "superseded_by_document_id": record.get("superseded_by_document_key"),
                "managed": True,
            }
        )
    return projected


def documents() -> list[dict[str, Any]]:
    """All known documents, with managed status changes applied."""
    manifest_documents = _manifest_documents()
    managed = _managed_documents()

    # An archived managed record supersedes the matching manifest entry, so the
    # dashboard cannot keep calling a replaced revision "active".
    managed_status = {
        (str(doc.get("document_code") or "").lower(), str(doc.get("revision") or "")): str(
            doc.get("document_status") or ""
        )
        for doc in managed
    }
    for document in manifest_documents:
        key = (
            str(document.get("document_code") or "").lower(),
            str(document.get("revision") or ""),
        )
        override = managed_status.get(key)
        if override:
            document["document_status"] = override

    return [*manifest_documents, *managed]


def documents_by_status(status: str) -> list[dict[str, Any]]:
    return [doc for doc in documents() if doc.get("document_status") == status]


def active_revisions() -> dict[str, str]:
    """Map document code -> active document id (e.g. QC-SOP-014 -> ...-rev04).

    A revision activated through the management interface always wins over the
    manifest entry for the same code.
    """
    manifest = load_manifest() or {}
    raw = manifest.get("active_revisions")
    merged: dict[str, str] = (
        {str(code): str(document_id) for code, document_id in raw.items()}
        if isinstance(raw, dict)
        else {}
    )
    merged.update(management_store.active_document_keys())
    return merged


def corpus_summary() -> dict[str, Any]:
    """Counts used by the status endpoint and the dashboard."""
    manifest = load_manifest() or {}
    summary = manifest.get("summary") if isinstance(manifest.get("summary"), dict) else {}
    active = documents_by_status("active")
    archived = documents_by_status("archived")
    managed_active_chunks = sum(
        int(document.get("chunk_count") or 0)
        for document in active
        if document.get("managed")
    )
    return {
        "manifest_available": bool(manifest),
        "generated_at": manifest.get("generated_at"),
        "active_document_count": len(active),
        "archived_document_count": len(archived),
        "processed_active_chunks": int(summary.get("active_chunks") or 0)
        + managed_active_chunks,
        "active_revisions": active_revisions(),
    }
