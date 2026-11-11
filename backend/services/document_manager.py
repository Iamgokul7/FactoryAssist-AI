"""Upload, processing and revision governance for managed SOP documents.

This module deliberately reuses the existing pipeline instead of duplicating it:

* ``pdf_processor.extract_document`` performs the PyMuPDF page extraction.
* ``text_chunker.chunk_document`` performs the page-scoped chunking.
* ``EmbeddingService.embed_documents`` produces the Gemini embeddings.
* ``VectorStore.upsert`` writes the chunks to the same ChromaDB collection.

What is new is the governance around it: every upload is validated, recorded,
processed into ``pending_review``, and only becomes searchable when an
authorised manager activates it. Pending, failed, rejected and archived
revisions never satisfy the retrieval filter.
"""

from __future__ import annotations

import hashlib
import logging
import re
import shutil
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Sequence

import pymupdf

from backend.core.config import settings
from backend.services import knowledge_base, management_store
from backend.services.auth_store import AuthStore, get_auth_store
from backend.services.document_models import DocumentSpec, ExtractedPage
from backend.services.embedding_service import EmbeddingError, EmbeddingService
from backend.services.gemini_client import GeminiNotConfiguredError
from backend.services.management_store import (
    CATEGORIES,
    STATUS_ACTIVE,
    STATUS_ARCHIVED,
    STATUS_FAILED,
    STATUS_PENDING_REVIEW,
    STATUS_PROCESSING,
    STATUS_REJECTED,
    DocumentNotFoundError,
    DocumentStore,
    document_key,
    get_document_store,
)
from backend.services.pdf_processor import extract_document
from backend.services.text_chunker import chunk_document
from backend.services.vector_store import VectorStore, VectorStoreError

logger = logging.getLogger(__name__)

DOCUMENT_CODE_PATTERN = re.compile(r"^[A-Z0-9]{2,8}(?:-[A-Z0-9]{2,8}){1,4}$")
REVISION_PATTERN = re.compile(r"^[0-9]{1,3}$")
MAX_PAGES = 300
MAX_TITLE_LENGTH = 200
MAX_DEPARTMENT_LENGTH = 80
MAX_DESCRIPTION_LENGTH = 1000

# Serialises activation/archive so two managers cannot interleave a revision
# switch for the same document code.
_ACTIVATION_LOCK = threading.Lock()

# Terms that indicate a manufacturing document. Used only as a review aid: a
# low score produces a warning, never an automatic rejection.
_MANUFACTURING_TERMS = (
    "sop",
    "procedure",
    "standard operating",
    "operator",
    "machine",
    "machining",
    "cnc",
    "spindle",
    "coolant",
    "tolerance",
    "inspection",
    "quality",
    "caliper",
    "maintenance",
    "lubrication",
    "lockout",
    "tagout",
    "safety",
    "ppe",
    "hazard",
    "plant",
    "production",
    "shop floor",
    "tool",
    "bearing",
    "revision",
    "department",
    "supervisor",
    "shift",
    "defect",
    "measurement",
)


class ManagementError(RuntimeError):
    """Base class for expected management failures with an HTTP status."""

    status_code = 400
    error_code = "invalid_request"

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class UploadValidationError(ManagementError):
    status_code = 400
    error_code = "invalid_upload"


class UnsupportedFileTypeError(UploadValidationError):
    status_code = 415
    error_code = "unsupported_file_type"


class FileTooLargeError(UploadValidationError):
    status_code = 413
    error_code = "file_too_large"


class DuplicateRevisionError(ManagementError):
    status_code = 409
    error_code = "duplicate_revision"


class DocumentStateError(ManagementError):
    status_code = 409
    error_code = "invalid_state"


class UnknownDocumentError(ManagementError):
    status_code = 404
    error_code = "document_not_found"


class StorageFailureError(ManagementError):
    status_code = 500
    error_code = "storage_failure"


@dataclass(slots=True)
class UploadMetadata:
    """Validated user-supplied metadata for one upload."""

    document_code: str
    document_title: str
    revision: str
    department: str
    category: str
    effective_date: str
    description: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "document_code": self.document_code,
            "document_title": self.document_title,
            "revision": self.revision,
            "department": self.department,
            "category": self.category,
            "effective_date": self.effective_date,
            "description": self.description,
        }


def validate_metadata(
    *,
    document_code: str,
    document_title: str,
    revision: str,
    department: str,
    category: str,
    effective_date: str,
    description: str = "",
) -> UploadMetadata:
    """Validate and normalise the upload form. Raises on the first problem."""
    code = (document_code or "").strip().upper()
    if not DOCUMENT_CODE_PATTERN.match(code):
        raise UploadMetadataError(
            "Document ID must look like QC-SOP-014 or MNT-MAN-CNC-02 "
            "(letters, digits and hyphens)."
        )

    title = " ".join((document_title or "").split())
    if len(title) < 3 or len(title) > MAX_TITLE_LENGTH:
        raise UploadMetadataError(f"Document title must be 3-{MAX_TITLE_LENGTH} characters.")

    revision_text = (revision or "").strip()
    if not REVISION_PATTERN.match(revision_text):
        raise UploadMetadataError("Revision must be a number, for example 05.")
    revision_normalised = revision_text.zfill(2)
    if int(revision_normalised) < 1:
        raise UploadMetadataError("Revision must be 1 or higher.")

    department_text = " ".join((department or "").split())
    if len(department_text) < 2 or len(department_text) > MAX_DEPARTMENT_LENGTH:
        raise UploadMetadataError(
            f"Department must be 2-{MAX_DEPARTMENT_LENGTH} characters."
        )

    category_text = (category or "").strip()
    if category_text not in CATEGORIES:
        raise UploadMetadataError(
            "Document category must be one of: " + ", ".join(CATEGORIES) + "."
        )

    try:
        parsed_date = date.fromisoformat((effective_date or "").strip())
    except ValueError as exc:
        raise UploadMetadataError("Effective date must be a valid date (YYYY-MM-DD).") from exc

    explanation = (description or "").strip()
    if len(explanation) > MAX_DESCRIPTION_LENGTH:
        raise UploadMetadataError(
            f"Description must be at most {MAX_DESCRIPTION_LENGTH} characters."
        )

    return UploadMetadata(
        document_code=code,
        document_title=title,
        revision=revision_normalised,
        department=department_text,
        category=category_text,
        effective_date=parsed_date.isoformat(),
        description=explanation,
    )


class UploadMetadataError(UploadValidationError):
    status_code = 422
    error_code = "invalid_metadata"


def validate_pdf_bytes(data: bytes, *, filename: str, content_type: str | None) -> None:
    """Cheap checks performed before anything is written to disk."""
    if not data:
        raise UploadValidationError("The uploaded file is empty.")

    size_limit = settings.max_upload_size_bytes
    if len(data) > size_limit:
        raise FileTooLargeError(
            f"The file is larger than the {settings.max_upload_size_mb} MB upload limit."
        )

    name = (filename or "").strip()
    if not name or not name.lower().endswith(".pdf"):
        raise UnsupportedFileTypeError("Only PDF files can be uploaded.")

    mime = (content_type or "").split(";")[0].strip().lower()
    allowed = {"application/pdf", "application/x-pdf", "application/octet-stream", ""}
    if mime not in allowed:
        raise UnsupportedFileTypeError(
            "The file must be a PDF (content type application/pdf)."
        )

    # The extension and MIME type are both client-supplied, so the file
    # signature is the check that actually matters.
    header = data[:1024]
    if b"%PDF-" not in header:
        raise UploadValidationError(
            "The file does not look like a valid PDF (missing PDF signature)."
        )


def inspect_pdf(path: Path) -> tuple[int, int, list[str]]:
    """Open a saved PDF and validate it is readable, unencrypted and has text.

    Returns ``(page_count, pages_with_text, warnings)``.
    """
    try:
        # Validate from memory: holding an open file handle here stops Windows
        # from deleting the file when validation later rejects it.
        document = pymupdf.open(stream=path.read_bytes(), filetype="pdf")
        try:
            if document.needs_pass:
                raise UploadValidationError("The PDF is password protected and cannot be processed.")
            page_count = document.page_count
            if page_count == 0:
                raise UploadValidationError("The PDF contains no pages.")
            if page_count > MAX_PAGES:
                raise UploadValidationError(
                    f"The PDF has {page_count} pages; the limit is {MAX_PAGES}."
                )

            pages_with_text = 0
            warnings: list[str] = []
            for page_number, page in enumerate(document, start=1):
                try:
                    text = (page.get_text("text") or "").strip()
                except Exception as exc:  # noqa: BLE001 - report, do not crash
                    warnings.append(f"page {page_number}: text extraction failed")
                    logger.warning("Page %s of %s could not be read: %s", page_number, path.name, type(exc).__name__)
                    continue
                if text:
                    pages_with_text += 1
        finally:
            document.close()
    except ManagementError:
        raise
    except Exception as exc:  # noqa: BLE001 - a corrupt PDF is a user error
        logger.warning("PDF validation failed for %s: %s", path.name, type(exc).__name__)
        raise UploadValidationError(
            "The PDF is corrupted or not a valid PDF document."
        ) from exc

    if pages_with_text == 0:
        raise UploadValidationError(
            "The PDF contains no extractable text. Scanned or image-only PDFs "
            "need a text layer before they can be indexed."
        )
    if pages_with_text < page_count:
        warnings.append(
            f"{page_count - pages_with_text} of {page_count} pages have no extractable text"
        )
    return page_count, pages_with_text, warnings


def classify_document(text: str) -> dict[str, Any]:
    """Rough manufacturing-relevance check used as a review aid."""
    sample = (text or "")[:8000].lower()
    if not sample:
        return {
            "related": False,
            "score": 0,
            "warning": "No text was available to classify this document.",
        }
    hits = sum(1 for term in _MANUFACTURING_TERMS if term in sample)
    related = hits >= 4
    warning = None
    if not related:
        warning = (
            "This document does not look like a manufacturing SOP, manual or "
            "instruction. Review it carefully before activation."
        )
    return {"related": related, "score": hits, "warning": warning}


def _safe_error(exc: Exception) -> str:
    """A user-facing message that never includes a path, key or traceback."""
    if isinstance(exc, ManagementError):
        return exc.message
    if isinstance(exc, GeminiNotConfiguredError):
        return (
            "The AI service is not configured, so the document could not be "
            "indexed. Ask the administrator to set GEMINI_API_KEY."
        )
    if isinstance(exc, EmbeddingError):
        return (
            "The embedding service failed, so the document was not indexed. "
            "Retry the processing when the service is available."
        )
    if isinstance(exc, VectorStoreError):
        return (
            "The document index could not be updated, so the upload was not "
            "indexed. Retry the processing."
        )
    return "Processing failed unexpectedly. Check the server log for details."


class DocumentManager:
    """Coordinates validation, processing, activation and archival."""

    def __init__(
        self,
        *,
        store: DocumentStore | None = None,
        auth: AuthStore | None = None,
        vector_store: VectorStore | None = None,
        embedder: Any | None = None,
    ) -> None:
        self.store = store or get_document_store()
        self.auth = auth or get_auth_store()
        self.vector_store = vector_store or VectorStore()
        self.embedder = embedder or EmbeddingService()

    # --- upload ---------------------------------------------------------

    def upload(
        self,
        *,
        data: bytes,
        filename: str,
        content_type: str | None,
        metadata: UploadMetadata,
        user: Any,
        ip: str | None = None,
    ) -> dict[str, Any]:
        try:
            validate_pdf_bytes(data, filename=filename, content_type=content_type)
        except ManagementError as exc:
            self.auth.audit(
                "upload_validation_failed",
                result="failure",
                username=user.username,
                user_id=user.user_id,
                document_key=document_key(metadata.document_code, metadata.revision),
                revision=metadata.revision,
                detail=exc.message,
                ip=ip,
            )
            raise

        key = document_key(metadata.document_code, metadata.revision)
        existing = self.store.get(key)
        if existing is not None:
            self.auth.audit(
                "upload_rejected",
                result="failure",
                username=user.username,
                user_id=user.user_id,
                document_key=key,
                revision=metadata.revision,
                detail="duplicate revision",
                ip=ip,
            )
            raise DuplicateRevisionError(
                f"Revision {metadata.revision} of {metadata.document_code} already "
                "exists. Upload the next revision number instead."
            )
        self._reject_manifest_duplicate(metadata)

        content_hash = hashlib.sha256(data).hexdigest()
        for record in self.store.all():
            if record.get("content_sha256") == content_hash and record.get("status") != STATUS_FAILED:
                raise DuplicateRevisionError(
                    "This exact PDF has already been uploaded as "
                    f"{record.get('document_code')} Rev {record.get('revision')}."
                )

        stored_name = f"{key}-{uuid.uuid4().hex[:8]}.pdf"
        uploads = Path(settings.uploads_directory)
        uploads.mkdir(parents=True, exist_ok=True)
        stored_path = (uploads / stored_name).resolve()

        # Resolve defensively: the generated name cannot escape the upload
        # directory, and this assertion keeps it that way if that changes.
        if uploads.resolve() not in stored_path.parents:
            raise StorageFailureError("The upload could not be stored safely.")

        try:
            with stored_path.open("xb") as handle:
                handle.write(data)
        except OSError as exc:
            logger.error("Could not save upload: %s", type(exc).__name__)
            raise StorageFailureError("The upload could not be saved.") from exc

        try:
            page_count, pages_with_text, warnings = inspect_pdf(stored_path)
        except ManagementError as exc:
            _remove_quietly(stored_path)
            self.auth.audit(
                "upload_validation_failed",
                result="failure",
                username=user.username,
                user_id=user.user_id,
                document_key=key,
                revision=metadata.revision,
                detail=exc.message,
                ip=ip,
            )
            raise

        record = self.store.add(
            {
                "document_key": key,
                "document_code": metadata.document_code,
                "document_title": metadata.document_title,
                "revision": metadata.revision,
                "department": metadata.department,
                "category": metadata.category,
                "description": metadata.description,
                "effective_date": metadata.effective_date,
                "status": STATUS_PROCESSING,
                "source_filename": _display_filename(filename),
                "stored_filename": stored_name,
                "stored_path": str(stored_path),
                "content_sha256": content_hash,
                "size_bytes": len(data),
                "page_count": page_count,
                "pages_with_text": pages_with_text,
                "chunk_count": 0,
                "uploaded_by": user.username,
                "uploaded_at": management_store.utc_now_iso(),
                "processed_at": None,
                "approved_by": None,
                "approved_at": None,
                "warnings": warnings,
                "error": None,
                "classification": None,
                "supersedes_document_key": None,
                "superseded_by_document_key": None,
            }
        )

        self.auth.audit(
            "upload_received",
            result="success",
            username=user.username,
            user_id=user.user_id,
            document_key=key,
            revision=metadata.revision,
            detail=f"{metadata.document_code} Rev {metadata.revision} queued for processing",
            ip=ip,
        )

        return self._process(key, stored_path, user=user, ip=ip)

    def _reject_manifest_duplicate(self, metadata: UploadMetadata) -> None:
        """Refuse a revision that already exists in the curated corpus."""
        for document in knowledge_base.documents():
            if document.get("managed"):
                continue
            same_code = (
                str(document.get("document_code") or "").lower()
                == metadata.document_code.lower()
            )
            same_revision = str(document.get("revision") or "") == metadata.revision
            if same_code and same_revision:
                raise DuplicateRevisionError(
                    f"{metadata.document_code} Rev {metadata.revision} is already part "
                    "of the controlled corpus."
                )

    # --- processing -----------------------------------------------------

    def retry(
        self, key: str, *, user: Any, ip: str | None = None
    ) -> dict[str, Any]:
        record = self._require(key)
        if record["status"] not in {STATUS_FAILED, STATUS_PENDING_REVIEW}:
            raise DocumentStateError(
                "Only failed uploads can be reprocessed. This document is "
                f"{record['status']}."
            )
        stored_path = Path(str(record.get("stored_path") or ""))
        if not stored_path.is_file():
            raise DocumentStateError(
                "The stored PDF for this upload is no longer available, so it "
                "cannot be reprocessed. Upload it again."
            )

        self.store.update(key, status=STATUS_PROCESSING, error=None)
        self.auth.audit(
            "processing_retried",
            result="success",
            username=user.username,
            user_id=user.user_id,
            document_key=key,
            revision=record.get("revision"),
            ip=ip,
        )
        return self._process(key, stored_path, user=user, ip=ip)

    def _process(
        self, key: str, pdf_path: Path, *, user: Any, ip: str | None = None
    ) -> dict[str, Any]:
        """Extract, chunk, embed and index one revision into ``pending_review``."""
        record = self.store.require(key)
        spec = DocumentSpec(
            document_id=key,
            document_title=str(record["document_title"]),
            document_code=str(record["document_code"]),
            revision=str(record["revision"]),
            document_type=str(record["category"]),
            source_filename=str(record.get("stored_filename") or pdf_path.name),
            document_status=STATUS_PENDING_REVIEW,
            effective_date=None,
        )

        try:
            document = extract_document(pdf_path, spec)
            if document.errors:
                raise UploadValidationError(
                    "The PDF text could not be extracted: " + "; ".join(document.errors[:3])
                )
            pages: list[ExtractedPage] = document.pages
            if not any(page.page_text.strip() for page in pages):
                raise UploadValidationError(
                    "The PDF contains no extractable text. Scanned or image-only "
                    "PDFs need a text layer before they can be indexed."
                )

            chunks = chunk_document(
                pages,
                document_code=spec.document_code,
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
            )
            if not chunks:
                raise UploadValidationError(
                    "No indexable text chunks could be produced from this PDF."
                )

            full_text = "\n".join(page.page_text for page in pages)
            classification = classify_document(full_text)

            reused = self._reuse_existing_embeddings(key, chunks)
            if not reused:
                vectors = self.embedder.embed_documents([chunk.chunk_text for chunk in chunks])
                if len(vectors) != len(chunks):
                    raise EmbeddingError("Embedding count did not match the chunk count.")
                from backend.services.vector_store import ChunkRecord

                self.vector_store.upsert(
                    [
                        ChunkRecord(
                            chunk_id=chunk.chunk_id,
                            chunk_text=chunk.chunk_text,
                            embedding=vector,
                            metadata={
                                "document_id": key,
                                "document_title": chunk.document_title,
                                "document_code": chunk.document_code,
                                "revision": chunk.revision,
                                "document_status": STATUS_PENDING_REVIEW,
                                "source_filename": chunk.source_filename,
                                "page_number": chunk.page_number,
                                "page_range": chunk.page_range,
                                "chunk_index": chunk.chunk_index,
                                "content_hash": hashlib.sha256(
                                    chunk.chunk_text.encode("utf-8")
                                ).hexdigest()[:16],
                                "managed": "yes",
                            },
                        )
                        for chunk, vector in zip(chunks, vectors)
                    ]
                )

            warnings = list(record.get("warnings") or [])
            if classification.get("warning"):
                warnings.append(str(classification["warning"]))

            updated = self.store.update(
                key,
                status=STATUS_PENDING_REVIEW,
                chunk_count=len(chunks),
                processed_at=management_store.utc_now_iso(),
                warnings=warnings,
                classification=classification,
                error=None,
                pages_with_text=sum(1 for page in pages if page.page_text.strip()),
            )
        except Exception as exc:  # noqa: BLE001 - every failure is recorded
            message = _safe_error(exc)
            logger.error(
                "Processing failed for %s: %s | %s",
                key,
                type(exc).__name__,
                str(exc)[:200],
            )
            try:
                self.vector_store.delete_by_document(key)
            except Exception:  # noqa: BLE001 - cleanup is best effort
                logger.warning("Could not clean up partial chunks for %s", key)
            updated = self.store.update(key, status=STATUS_FAILED, error=message, chunk_count=0)
            self.auth.audit(
                "processing_failed",
                result="failure",
                username=user.username,
                user_id=user.user_id,
                document_key=key,
                revision=record.get("revision"),
                detail=message,
                ip=ip,
            )
            return management_store.public_view(updated)

        self.auth.audit(
            "processing_succeeded",
            result="success",
            username=user.username,
            user_id=user.user_id,
            document_key=key,
            revision=record.get("revision"),
            detail=f"{len(chunks)} chunks indexed, awaiting review",
            ip=ip,
        )
        return management_store.public_view(updated)

    def _reuse_existing_embeddings(self, key: str, chunks: Sequence[Any]) -> bool:
        """Skip re-embedding when the identical chunks are already indexed.

        A retry after a later failure therefore does not spend embedding calls
        again on the same text.
        """
        try:
            existing = self.vector_store.metadata_for_document(key)
        except VectorStoreError:
            return False
        if len(existing) != len(chunks):
            return False
        for chunk in chunks:
            metadata = existing.get(chunk.chunk_id)
            if metadata is None:
                return False
            expected = hashlib.sha256(chunk.chunk_text.encode("utf-8")).hexdigest()[:16]
            if metadata.get("content_hash") != expected:
                return False
        return True

    # --- governance -----------------------------------------------------

    def activate(self, key: str, *, user: Any, ip: str | None = None) -> dict[str, Any]:
        """Make one pending revision active and archive the revision it replaces."""
        with _ACTIVATION_LOCK:
            record = self._require(key)
            if record["status"] != STATUS_PENDING_REVIEW:
                raise DocumentStateError(
                    f"Only documents pending review can be activated. This document is "
                    f"{record['status']}."
                )

            try:
                indexed = self.vector_store.metadata_for_document(key)
            except VectorStoreError as exc:
                raise StorageFailureError(
                    "The document index could not be checked, so the document was "
                    "not activated."
                ) from exc
            if len(indexed) != int(record.get("chunk_count") or 0) or not indexed:
                raise DocumentStateError(
                    "The document's indexed chunks do not match its records. "
                    "Reprocess the document before activating it."
                )

            active_now = [
                other
                for other in self.store.revisions_of(str(record["document_code"]))
                if other.get("status") == STATUS_ACTIVE
            ]
            previous = active_now[0] if active_now else None
            if previous and previous["document_key"] == key:
                raise DocumentStateError("This revision is already active.")

            now = management_store.utc_now_iso()
            changes: dict[str, dict[str, Any]] = {
                key: {
                    "status": STATUS_ACTIVE,
                    "approved_by": user.username,
                    "approved_at": now,
                    "supersedes_document_key": previous["document_key"] if previous else None,
                    "error": None,
                }
            }
            if previous:
                changes[previous["document_key"]] = {
                    "status": STATUS_ARCHIVED,
                    "archived_by": user.username,
                    "archived_at": now,
                    "superseded_by_document_key": key,
                }

            # 1. Flip the new revision's chunks to active. The retrieval guard
            #    still maps the code to the old revision, so the two-active
            #    window cannot leak the new revision into an answer.
            try:
                self.vector_store.set_document_status(key, STATUS_ACTIVE)
            except VectorStoreError as exc:
                raise StorageFailureError(
                    "The document index could not be updated, so the revision was "
                    "not activated."
                ) from exc

            # 2. Single atomic write commits the switch: exactly one active
            #    revision, and the superseded one archived.
            try:
                applied = self.store.apply(changes)
            except Exception as exc:  # noqa: BLE001 - roll the index back
                logger.error("Activation commit failed for %s: %s", key, type(exc).__name__)
                try:
                    self.vector_store.set_document_status(key, STATUS_PENDING_REVIEW)
                except VectorStoreError:
                    logger.error("Could not roll back chunk status for %s", key)
                raise StorageFailureError(
                    "The revision could not be activated because the document "
                    "records could not be saved. Nothing was changed."
                ) from exc

            # 3. Remove the superseded revision's chunks. The records already
            #    exclude them from retrieval, so a failure here is logged and
            #    the activation still stands.
            if previous:
                try:
                    self.vector_store.delete_by_document(previous["document_key"])
                except VectorStoreError:
                    logger.warning(
                        "Superseded chunks for %s could not be removed; they remain "
                        "filtered out by document status",
                        previous["document_key"],
                    )

            updated = applied[key]
            self.auth.audit(
                "revision_activated",
                result="success",
                username=user.username,
                user_id=user.user_id,
                document_key=key,
                revision=record.get("revision"),
                detail=(
                    f"{record['document_code']} Rev {record['revision']} activated"
                    + (f"; Rev {previous['revision']} archived" if previous else "")
                ),
                ip=ip,
            )
            if previous:
                self.auth.audit(
                    "revision_archived",
                    result="success",
                    username=user.username,
                    user_id=user.user_id,
                    document_key=previous["document_key"],
                    revision=previous.get("revision"),
                    detail=f"Superseded by {key}",
                    ip=ip,
                )
            return management_store.public_view(updated)

    def archive(
        self,
        key: str,
        *,
        user: Any,
        ip: str | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """Retire an active revision, refusing to leave the code without one."""
        with _ACTIVATION_LOCK:
            record = self._require(key)
            if record["status"] != STATUS_ACTIVE:
                raise DocumentStateError(
                    f"Only active documents can be archived. This document is "
                    f"{record['status']}."
                )

            siblings = [
                other
                for other in self.store.revisions_of(str(record["document_code"]))
                if other.get("status") == STATUS_ACTIVE and other["document_key"] != key
            ]
            if siblings:
                raise DocumentStateError(
                    "Another revision of this document is active. Activate the "
                    "revision you want instead; activation archives this one."
                )
            if not force and not self._has_replacement(key, record):
                raise DocumentStateError(
                    "This is the only active revision of the document. Upload and "
                    "activate a replacement first, or archive it with force=true "
                    "as an administrator."
                )
            if force and getattr(user, "role", "") != "admin":
                raise DocumentStateError(
                    "Only an administrator can archive the last active revision."
                )

            now = management_store.utc_now_iso()
            updated = self.store.update(
                key,
                status=STATUS_ARCHIVED,
                archived_by=user.username,
                archived_at=now,
            )

            try:
                self.vector_store.delete_by_document(key)
            except VectorStoreError:
                logger.warning(
                    "Chunks for archived document %s could not be removed; they are "
                    "still excluded from retrieval by document status",
                    key,
                )

            self.auth.audit(
                "revision_archived",
                result="success",
                username=user.username,
                user_id=user.user_id,
                document_key=key,
                revision=record.get("revision"),
                detail="archived by manager" + (" (forced)" if force else ""),
                ip=ip,
            )
            return management_store.public_view(updated)

    def _has_replacement(self, key: str, record: dict[str, Any]) -> bool:
        """Whether a newer revision exists that could take over."""
        for other in self.store.revisions_of(str(record["document_code"])):
            if other["document_key"] == key:
                continue
            if other.get("status") in {STATUS_ACTIVE, STATUS_PENDING_REVIEW}:
                return True
        return False

    def reject(
        self,
        key: str,
        *,
        user: Any,
        reason: str = "",
        ip: str | None = None,
    ) -> dict[str, Any]:
        """Reject a pending revision so it can never be activated as-is."""
        record = self._require(key)
        if record["status"] != STATUS_PENDING_REVIEW:
            raise DocumentStateError(
                f"Only documents pending review can be rejected. This document is "
                f"{record['status']}."
            )
        reason_text = " ".join((reason or "").split())[:300]
        updated = self.store.update(
            key,
            status=STATUS_REJECTED,
            rejected_by=user.username,
            rejected_at=management_store.utc_now_iso(),
            rejection_reason=reason_text or None,
        )
        try:
            self.vector_store.delete_by_document(key)
        except VectorStoreError:
            logger.warning("Rejected chunks for %s could not be removed", key)

        self.auth.audit(
            "revision_rejected",
            result="success",
            username=user.username,
            user_id=user.user_id,
            document_key=key,
            revision=record.get("revision"),
            detail=reason_text or "rejected without a reason",
            ip=ip,
        )
        return management_store.public_view(updated)

    def update_metadata(
        self,
        key: str,
        *,
        user: Any,
        changes: dict[str, Any],
        ip: str | None = None,
    ) -> dict[str, Any]:
        """Edit presentation metadata. Document code and revision are immutable."""
        record = self._require(key)
        allowed = {"document_title", "department", "category", "effective_date", "description"}
        unknown = set(changes) - allowed
        if unknown:
            raise UploadValidationError(
                "These fields cannot be changed: " + ", ".join(sorted(unknown))
            )

        merged = {
            "document_title": changes.get("document_title", record["document_title"]),
            "department": changes.get("department", record["department"]),
            "category": changes.get("category", record["category"]),
            "effective_date": changes.get("effective_date", record["effective_date"]),
            "description": changes.get("description", record.get("description") or ""),
        }
        validated = validate_metadata(
            document_code=str(record["document_code"]),
            document_title=str(merged["document_title"]),
            revision=str(record["revision"]),
            department=str(merged["department"]),
            category=str(merged["category"]),
            effective_date=str(merged["effective_date"]),
            description=str(merged["description"]),
        )

        updated = self.store.update(
            key,
            document_title=validated.document_title,
            department=validated.department,
            category=validated.category,
            effective_date=validated.effective_date,
            description=validated.description,
        )
        if record["status"] in {STATUS_ACTIVE, STATUS_PENDING_REVIEW}:
            try:
                self.vector_store.update_chunk_metadata(
                    key,
                    {
                        "document_title": validated.document_title,
                        "revision": str(record["revision"]),
                    },
                )
            except VectorStoreError:
                logger.warning("Chunk metadata for %s could not be refreshed", key)

        self.auth.audit(
            "metadata_changed",
            result="success",
            username=user.username,
            user_id=user.user_id,
            document_key=key,
            revision=record.get("revision"),
            detail=", ".join(sorted(changes)) or "no changes",
            ip=ip,
        )
        return management_store.public_view(updated)

    # --- helpers --------------------------------------------------------

    def _require(self, key: str) -> dict[str, Any]:
        try:
            return self.store.require(key)
        except DocumentNotFoundError as exc:
            raise UnknownDocumentError(str(exc)) from exc

    def list_documents(
        self,
        *,
        status: str | None = None,
        query: str | None = None,
        department: str | None = None,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        records = self.store.all()
        needle = (query or "").strip().lower()
        filtered: list[dict[str, Any]] = []
        for record in records:
            if status and record.get("status") != status:
                continue
            if department and str(record.get("department", "")).lower() != department.lower():
                continue
            if category and record.get("category") != category:
                continue
            if needle:
                haystack = " ".join(
                    str(record.get(field, ""))
                    for field in ("document_code", "document_title", "revision", "department", "description")
                ).lower()
                if needle not in haystack:
                    continue
            filtered.append(record)
        filtered.sort(
            key=lambda item: (str(item.get("uploaded_at") or ""), str(item.get("document_key"))),
            reverse=True,
        )
        return [management_store.public_view(record) for record in filtered]

    def stats(self) -> dict[str, Any]:
        counts = self.store.counts()
        total = sum(counts.values())
        return {
            "total": total,
            "active": counts.get(STATUS_ACTIVE, 0),
            "pending_review": counts.get(STATUS_PENDING_REVIEW, 0),
            "processing": counts.get(STATUS_PROCESSING, 0),
            "archived": counts.get(STATUS_ARCHIVED, 0),
            "rejected": counts.get(STATUS_REJECTED, 0),
            "failed": counts.get(STATUS_FAILED, 0),
        }

    def revisions(self, code: str) -> list[dict[str, Any]]:
        records = self.store.revisions_of(code)
        if not records:
            raise UnknownDocumentError(f"No revisions found for '{code}'.")
        return [management_store.public_view(record) for record in records]


def _remove_quietly(path: Path, *, attempts: int = 5) -> None:
    """Delete a rejected upload without masking the validation error.

    Windows keeps the reader's handle (or an antivirus scan) for a moment after
    validation fails, so removal is retried briefly before giving up. A file that
    still cannot be deleted is logged: it has a unique generated name and no
    record ever references it.
    """
    for attempt in range(attempts):
        try:
            path.unlink(missing_ok=True)
            return
        except OSError as exc:
            if attempt == attempts - 1:
                logger.warning(
                    "Could not remove rejected upload after %s attempts: %s",
                    attempts,
                    type(exc).__name__,
                )
                return
            time.sleep(0.2 * (attempt + 1))


def _display_filename(filename: str) -> str:
    """Keep only the base name, without control characters."""
    name = Path((filename or "").replace("\\", "/")).name
    cleaned = "".join(char for char in name if char.isprintable())[:160]
    return cleaned or "upload.pdf"


def recover_interrupted_processing() -> int:
    """Mark uploads left in PROCESSING by a crash or restart as failed."""
    store = get_document_store()
    interrupted = 0
    for record in store.all():
        if record.get("status") != STATUS_PROCESSING:
            continue
        store.update(
            record["document_key"],
            status=STATUS_FAILED,
            error=(
                "Processing was interrupted (the server stopped before it "
                "finished). Reprocess the document to try again."
            ),
        )
        interrupted += 1
    if interrupted:
        logger.warning("Marked %s interrupted upload(s) as failed", interrupted)
    return interrupted


def storage_locations() -> dict[str, str]:
    """Human-readable storage paths for the setup documentation."""
    return {
        "uploads": str(settings.uploads_directory),
        "records": str(settings.document_records_path),
        "database": str(settings.auth_database_path),
    }


def copy_to_corpus_folder(record: dict[str, Any], target: Path) -> str | None:
    """Optional convenience: mirror an active PDF into a corpus folder.

    Not called automatically: the controlled corpus folders are managed by the
    Stage 2 pipeline, and silently dropping files there would make that
    pipeline report them as unregistered. Kept as an explicit helper for
    operators who want a browsable folder of approved documents.
    """
    source = Path(str(record.get("stored_path") or ""))
    if not source.is_file():
        return None
    target.mkdir(parents=True, exist_ok=True)
    destination = target / f"{record['document_key']}.pdf"
    shutil.copy2(source, destination)
    return str(destination)
