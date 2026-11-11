"""Document-management API: upload, review, activation and archival.

Every route requires an authenticated manager (``ADMIN`` or ``SOP_MANAGER``);
metadata edits require ``ADMIN``. Mutating routes additionally require the
session's CSRF token. Failures are returned as short, safe messages: no
filesystem paths, API keys or exception tracebacks reach the browser.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.api.deps import client_ip, get_document_manager, require_admin, require_manager
from backend.core.config import settings
from backend.services.auth_store import SessionUser, get_auth_store
from backend.services.document_manager import (
    ManagementError,
    UploadMetadata,
    DocumentManager,
    storage_locations,
    validate_metadata,
)
from backend.services.management_store import (
    CATEGORIES,
    DEFAULT_DEPARTMENTS,
    DOCUMENT_STATUSES,
    DocumentNotFoundError,
    get_document_store,
    public_view,
    status_label,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


class RejectRequest(BaseModel):
    reason: str = Field("", max_length=300)


class MetadataUpdateRequest(BaseModel):
    document_title: str | None = Field(None, max_length=200)
    department: str | None = Field(None, max_length=80)
    category: str | None = Field(None, max_length=80)
    effective_date: str | None = Field(None, max_length=20)
    description: str | None = Field(None, max_length=1000)


def _fail(exc: ManagementError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("", summary="List document revisions")
def list_documents(
    status: str | None = None,
    q: str | None = None,
    department: str | None = None,
    category: str | None = None,
    session: SessionUser = Depends(require_manager),
    manager: DocumentManager = Depends(get_document_manager),
) -> dict[str, Any]:
    """Searchable, filterable document list for the management table."""
    if status and status not in DOCUMENT_STATUSES:
        raise HTTPException(status_code=422, detail="Unknown document status filter.")
    documents = manager.list_documents(
        status=status, query=q, department=department, category=category
    )
    return {"documents": documents, "count": len(documents), "stats": manager.stats()}


@router.get("/stats", summary="Document management counters")
def document_stats(
    session: SessionUser = Depends(require_manager),
    manager: DocumentManager = Depends(get_document_manager),
) -> dict[str, Any]:
    return manager.stats()


@router.get("/meta", summary="Form options and governance rules")
def document_meta(session: SessionUser = Depends(require_manager)) -> dict[str, Any]:
    return {
        "categories": list(CATEGORIES),
        "departments": list(DEFAULT_DEPARTMENTS),
        "statuses": list(DOCUMENT_STATUSES),
        "max_upload_size_mb": settings.max_upload_size_mb,
        "storage": storage_locations(),
    }


@router.post("/upload", status_code=201, summary="Upload and process a PDF")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    document_code: str = Form(...),
    document_title: str = Form(...),
    revision: str = Form(...),
    department: str = Form(...),
    category: str = Form(...),
    effective_date: str = Form(...),
    description: str = Form(""),
    session: SessionUser = Depends(require_manager),
    manager: DocumentManager = Depends(get_document_manager),
) -> dict[str, Any]:
    """Validate, store, extract, embed and queue one revision for review."""
    try:
        metadata: UploadMetadata = validate_metadata(
            document_code=document_code,
            document_title=document_title,
            revision=revision,
            department=department,
            category=category,
            effective_date=effective_date,
            description=description,
        )
    except ManagementError as exc:
        get_auth_store().audit(
            "upload_validation_failed",
            result="failure",
            username=session.username,
            user_id=session.user_id,
            document_key=document_code,
            revision=revision,
            detail=exc.message,
            ip=client_ip(request),
        )
        raise _fail(exc) from exc

    limit = settings.max_upload_size_bytes
    try:
        data = await file.read(limit + 1)
    except Exception as exc:  # noqa: BLE001 - malformed multipart body
        logger.warning("Upload body could not be read: %s", type(exc).__name__)
        raise HTTPException(status_code=400, detail="The upload could not be read.") from exc
    finally:
        await file.close()

    try:
        document = manager.upload(
            data=data,
            filename=file.filename or "",
            content_type=file.content_type,
            metadata=metadata,
            user=session,
            ip=client_ip(request),
        )
    except ManagementError as exc:
        raise _fail(exc) from exc
    except Exception as exc:  # noqa: BLE001 - never leak internals
        logger.error("Unhandled upload failure: %s", type(exc).__name__)
        raise HTTPException(
            status_code=500, detail="The upload could not be processed. Check the server log."
        ) from exc

    return {"document": document, "message": _upload_message(document)}


def _upload_message(document: dict[str, Any]) -> str:
    if document.get("status") == "failed":
        return "The upload was stored but processing failed. See the error and retry."
    return (
        f"{document.get('document_code')} Rev {document.get('revision')} processed "
        "and is awaiting review. It is not searchable until it is activated."
    )


@router.get("/{document_key}", summary="Document details")
def get_document(
    document_key: str,
    session: SessionUser = Depends(require_manager),
    manager: DocumentManager = Depends(get_document_manager),
) -> dict[str, Any]:
    try:
        record = manager.store.require(document_key)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    revisions = manager.store.revisions_of(str(record["document_code"]))
    return {
        "document": public_view(record),
        "revisions": [public_view(item) for item in revisions],
    }


@router.get("/{document_key}/status", summary="Processing status")
def document_status(
    document_key: str,
    session: SessionUser = Depends(require_manager),
    manager: DocumentManager = Depends(get_document_manager),
) -> dict[str, Any]:
    try:
        record = manager.store.require(document_key)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "document_key": record["document_key"],
        "status": record.get("status"),
        "status_label": status_label(str(record.get("status", ""))),
        "chunk_count": record.get("chunk_count"),
        "page_count": record.get("page_count"),
        "error": record.get("error"),
        "processed_at": record.get("processed_at"),
        "approved_by": record.get("approved_by"),
        "approved_at": record.get("approved_at"),
    }


@router.get("/{document_key}/revisions", summary="Revision history")
def document_revisions(
    document_key: str,
    session: SessionUser = Depends(require_manager),
    manager: DocumentManager = Depends(get_document_manager),
) -> dict[str, Any]:
    record = get_document_store().get(document_key)
    if record is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    try:
        revisions = manager.revisions(str(record["document_code"]))
    except ManagementError as exc:
        raise _fail(exc) from exc
    return {"document_code": record["document_code"], "revisions": revisions}


@router.get("/{document_key}/file", summary="Download the stored PDF")
def download_document(
    document_key: str,
    session: SessionUser = Depends(require_manager),
) -> FileResponse:
    record = get_document_store().get(document_key)
    if record is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    uploads = Path(settings.uploads_directory).resolve()
    stored = Path(str(record.get("stored_path") or "")).resolve()
    if uploads not in stored.parents or not stored.is_file():
        raise HTTPException(status_code=404, detail="The stored PDF is not available.")

    return FileResponse(
        stored,
        media_type="application/pdf",
        filename=str(record.get("source_filename") or "document.pdf"),
    )


@router.post("/{document_key}/activate", summary="Activate a pending revision")
def activate_document(
    document_key: str,
    request: Request,
    session: SessionUser = Depends(require_manager),
    manager: DocumentManager = Depends(get_document_manager),
) -> dict[str, Any]:
    try:
        document = manager.activate(document_key, user=session, ip=client_ip(request))
    except ManagementError as exc:
        raise _fail(exc) from exc
    return {
        "document": document,
        "message": (
            f"{document['document_code']} Rev {document['revision']} is now active. "
            "The previous revision has been archived."
        ),
    }


@router.post("/{document_key}/archive", summary="Archive an active revision")
def archive_document(
    document_key: str,
    request: Request,
    force: bool = False,
    session: SessionUser = Depends(require_manager),
    manager: DocumentManager = Depends(get_document_manager),
) -> dict[str, Any]:
    try:
        document = manager.archive(
            document_key, user=session, ip=client_ip(request), force=force
        )
    except ManagementError as exc:
        raise _fail(exc) from exc
    return {"document": document, "message": "The revision is archived and no longer searchable."}


@router.post("/{document_key}/reject", summary="Reject a pending revision")
def reject_document(
    document_key: str,
    payload: RejectRequest,
    request: Request,
    session: SessionUser = Depends(require_manager),
    manager: DocumentManager = Depends(get_document_manager),
) -> dict[str, Any]:
    try:
        document = manager.reject(
            document_key, user=session, reason=payload.reason, ip=client_ip(request)
        )
    except ManagementError as exc:
        raise _fail(exc) from exc
    return {"document": document, "message": "The revision is rejected and cannot be activated."}


@router.post("/{document_key}/retry", summary="Reprocess a failed upload")
def retry_document(
    document_key: str,
    request: Request,
    session: SessionUser = Depends(require_manager),
    manager: DocumentManager = Depends(get_document_manager),
) -> dict[str, Any]:
    try:
        document = manager.retry(document_key, user=session, ip=client_ip(request))
    except ManagementError as exc:
        raise _fail(exc) from exc
    return {"document": document, "message": _upload_message(document)}


@router.patch("/{document_key}", summary="Edit document metadata (administrator)")
def update_document(
    document_key: str,
    payload: MetadataUpdateRequest,
    request: Request,
    session: SessionUser = Depends(require_admin),
    manager: DocumentManager = Depends(get_document_manager),
) -> dict[str, Any]:
    changes = {key: value for key, value in payload.model_dump().items() if value is not None}
    if not changes:
        raise HTTPException(status_code=422, detail="No changes were supplied.")
    try:
        document = manager.update_metadata(
            document_key, user=session, changes=changes, ip=client_ip(request)
        )
    except ManagementError as exc:
        raise _fail(exc) from exc
    return {"document": document, "message": "Document metadata updated."}
