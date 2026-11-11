"""Durable record of every uploaded document revision and its governance state.

The Stage 2 manifest stays the source of truth for the original, curated
corpus. This store adds documents uploaded through the management interface:

    PROCESSING -> PENDING_REVIEW -> ACTIVE -> ARCHIVED
                       |              |
                       +-> REJECTED   +-> ARCHIVED (replaced by a newer revision)
                       +-> FAILED

Only ``ACTIVE`` records are ever eligible for employee retrieval; the check is
enforced in the retrieval service, not in the browser.

A single JSON file is used instead of a second database because the records are
small, are written only by management actions, and must be readable by the
retrieval path without opening SQLite. Writes go through a temporary file and
``os.replace`` so a crash cannot leave a half-written record set.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.core.config import settings

logger = logging.getLogger(__name__)

STATUS_PROCESSING = "processing"
STATUS_PENDING_REVIEW = "pending_review"
STATUS_ACTIVE = "active"
STATUS_ARCHIVED = "archived"
STATUS_REJECTED = "rejected"
STATUS_FAILED = "failed"

DOCUMENT_STATUSES: tuple[str, ...] = (
    STATUS_PROCESSING,
    STATUS_PENDING_REVIEW,
    STATUS_ACTIVE,
    STATUS_ARCHIVED,
    STATUS_REJECTED,
    STATUS_FAILED,
)

# Statuses that must never be retrieved by the assistant.
NON_RETRIEVABLE_STATUSES: frozenset[str] = frozenset(
    {STATUS_PROCESSING, STATUS_PENDING_REVIEW, STATUS_ARCHIVED, STATUS_REJECTED, STATUS_FAILED}
)

CATEGORY_MANUFACTURING_SOP = "Manufacturing SOP"
CATEGORY_QUALITY_MANUAL = "Quality Manual"
CATEGORY_SAFETY_MANUAL = "Safety Manual"
CATEGORY_MAINTENANCE_MANUAL = "Maintenance Manual"
CATEGORY_WORK_INSTRUCTION = "Work Instruction"

CATEGORIES: tuple[str, ...] = (
    CATEGORY_MANUFACTURING_SOP,
    CATEGORY_QUALITY_MANUAL,
    CATEGORY_SAFETY_MANUAL,
    CATEGORY_MAINTENANCE_MANUAL,
    CATEGORY_WORK_INSTRUCTION,
)

DEFAULT_DEPARTMENTS: tuple[str, ...] = (
    "Production",
    "Quality",
    "Maintenance",
    "Safety",
    "Engineering",
    "Stores",
)

# Fields exposed to API clients. Storage-only paths are deliberately excluded.
_PUBLIC_FIELDS: tuple[str, ...] = (
    "document_key",
    "document_code",
    "document_title",
    "revision",
    "department",
    "category",
    "description",
    "effective_date",
    "status",
    "status_label",
    "source_filename",
    "page_count",
    "chunk_count",
    "uploaded_by",
    "uploaded_at",
    "processed_at",
    "approved_by",
    "approved_at",
    "archived_by",
    "archived_at",
    "rejected_by",
    "rejected_at",
    "rejection_reason",
    "error",
    "warnings",
    "classification",
    "supersedes_document_key",
    "superseded_by_document_key",
    "size_bytes",
    "updated_at",
)


class DuplicateDocumentError(RuntimeError):
    """Raised when a document code and revision pair already exists."""


class DocumentNotFoundError(RuntimeError):
    """Raised when a document key is unknown."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def document_key(code: str, revision: str) -> str:
    """Stable, URL-safe key such as ``qc-sop-014-rev05``."""
    return f"{code.strip().lower()}-rev{str(revision).strip().zfill(2)}"


class DocumentStore:
    """All uploaded document revisions, persisted as one JSON file."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or settings.document_records_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._records: dict[str, dict[str, Any]] | None = None

    # --- persistence ---

    def _load(self) -> dict[str, dict[str, Any]]:
        if self._records is not None:
            return self._records
        records: dict[str, dict[str, Any]] = {}
        if self.path.is_file():
            try:
                with self.path.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                raw = payload.get("documents") if isinstance(payload, dict) else None
                if isinstance(raw, list):
                    records = {
                        str(item["document_key"]): item
                        for item in raw
                        if isinstance(item, dict) and item.get("document_key")
                    }
            except (OSError, json.JSONDecodeError, KeyError) as exc:
                logger.error(
                    "Document records could not be read (%s); keeping a copy and "
                    "starting empty",
                    type(exc).__name__,
                )
                backup = self.path.with_suffix(f".corrupt-{int(datetime.now().timestamp())}.json")
                try:
                    self.path.replace(backup)
                except OSError:  # pragma: no cover - best effort
                    pass
        self._records = records
        return records

    def _write(self) -> None:
        records = self._load()
        payload = {
            "updated_at": utc_now_iso(),
            "count": len(records),
            "documents": sorted(records.values(), key=lambda item: item["document_key"]),
        }
        temporary = self.path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, self.path)

    # --- reads ---

    def all(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(record) for record in self._load().values()]

    def get(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._load().get(key)
            return dict(record) if record else None

    def require(self, key: str) -> dict[str, Any]:
        record = self.get(key)
        if record is None:
            raise DocumentNotFoundError(f"No document with key '{key}'.")
        return record

    def revisions_of(self, code: str) -> list[dict[str, Any]]:
        code = code.strip().lower()
        with self._lock:
            records = [
                dict(record)
                for record in self._load().values()
                if str(record.get("document_code", "")).lower() == code
            ]
        return sorted(records, key=lambda record: str(record.get("revision", "")))

    def find(self, code: str, revision: str) -> dict[str, Any] | None:
        key = document_key(code, revision)
        return self.get(key)

    def active_revisions(self) -> dict[str, str]:
        """Map document code (as stored) -> active document key."""
        mapping: dict[str, str] = {}
        with self._lock:
            for record in self._load().values():
                if record.get("status") == STATUS_ACTIVE:
                    mapping[str(record["document_code"])] = str(record["document_key"])
        return mapping

    def counts(self) -> dict[str, int]:
        counts = {status: 0 for status in DOCUMENT_STATUSES}
        with self._lock:
            for record in self._load().values():
                status = str(record.get("status", ""))
                counts[status] = counts.get(status, 0) + 1
        return counts

    # --- writes ---

    def add(self, record: dict[str, Any]) -> dict[str, Any]:
        key = str(record["document_key"])
        code = str(record["document_code"])
        revision = str(record["revision"])
        with self._lock:
            records = self._load()
            if key in records:
                raise DuplicateDocumentError(
                    f"Revision {revision} of {code} already exists."
                )
            for existing in records.values():
                if (
                    str(existing.get("document_code", "")).lower() == code.lower()
                    and str(existing.get("revision", "")) == revision
                ):
                    raise DuplicateDocumentError(
                        f"Revision {revision} of {code} already exists."
                    )
            record = {
                "document_key": key,
                "document_code": code,
                "revision": revision,
                "created_at": utc_now_iso(),
                "updated_at": utc_now_iso(),
                **record,
            }
            records[key] = record
            self._write()
            return dict(record)

    def apply(self, changes: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Apply several record changes in one atomic write.

        Used by revision activation so the new revision becoming active and the
        old one becoming archived cannot be observed separately.
        """
        if not changes:
            return {}
        with self._lock:
            records = self._load()
            missing = [key for key in changes if key not in records]
            if missing:
                raise DocumentNotFoundError(f"Unknown document key(s): {', '.join(missing)}")
            now = utc_now_iso()
            for key, fields in changes.items():
                records[key].update(fields)
                records[key]["updated_at"] = now
            self._write()
            return {key: dict(records[key]) for key in changes}

    def update(self, key: str, **changes: Any) -> dict[str, Any]:
        with self._lock:
            records = self._load()
            record = records.get(key)
            if record is None:
                raise DocumentNotFoundError(f"No document with key '{key}'.")
            record.update(changes)
            record["updated_at"] = utc_now_iso()
            self._write()
            return dict(record)


def public_view(record: dict[str, Any]) -> dict[str, Any]:
    """API-safe projection of a record (no filesystem paths)."""
    view = {field: record.get(field) for field in _PUBLIC_FIELDS}
    view["status_label"] = status_label(str(record.get("status", "")))
    return view


_STATUS_LABELS = {
    STATUS_PROCESSING: "Processing",
    STATUS_PENDING_REVIEW: "Pending review",
    STATUS_ACTIVE: "Active",
    STATUS_ARCHIVED: "Archived",
    STATUS_REJECTED: "Rejected",
    STATUS_FAILED: "Failed",
}


def status_label(status: str) -> str:
    return _STATUS_LABELS.get(status, status.replace("_", " ").title())


# --- module-level shared instance -------------------------------------------

_store: DocumentStore | None = None


def get_document_store() -> DocumentStore:
    global _store
    if _store is None or _store.path != Path(settings.document_records_path):
        _store = DocumentStore()
    return _store


def reset_document_store() -> None:
    global _store
    _store = None


def active_document_keys() -> dict[str, str]:
    """Code -> active document key, read from the managed store."""
    return get_document_store().active_revisions()
