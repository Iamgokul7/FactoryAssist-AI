"""Read-only access to the processed document manifest.

The manifest produced by the Stage 2 pipeline is the source of truth for
document metadata and for which revision of each document is active.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from backend.core.config import settings

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


def documents() -> list[dict[str, Any]]:
    """All processed documents, trimmed to the fields the API and UI need."""
    manifest = load_manifest() or {}
    raw = manifest.get("documents")
    if not isinstance(raw, list):
        return []
    return [
        {field: document.get(field) for field in _DOCUMENT_FIELDS}
        for document in raw
        if isinstance(document, dict)
    ]


def documents_by_status(status: str) -> list[dict[str, Any]]:
    return [doc for doc in documents() if doc.get("document_status") == status]


def active_revisions() -> dict[str, str]:
    """Map document code -> active document id (e.g. QC-SOP-014 -> ...-rev04)."""
    manifest = load_manifest() or {}
    raw = manifest.get("active_revisions")
    if not isinstance(raw, dict):
        return {}
    return {str(code): str(document_id) for code, document_id in raw.items()}


def corpus_summary() -> dict[str, Any]:
    """Counts used by the status endpoint and the dashboard."""
    manifest = load_manifest() or {}
    summary = manifest.get("summary") if isinstance(manifest.get("summary"), dict) else {}
    active = documents_by_status("active")
    archived = documents_by_status("archived")
    return {
        "manifest_available": bool(manifest),
        "generated_at": manifest.get("generated_at"),
        "active_document_count": len(active),
        "archived_document_count": len(archived),
        "processed_active_chunks": int(summary.get("active_chunks") or 0),
        "active_revisions": active_revisions(),
    }
