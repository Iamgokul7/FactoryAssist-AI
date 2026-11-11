"""Shared FastAPI dependencies for authentication, CSRF and document management.

Every permission is enforced here, on the server. The frontend hides controls it
knows will be rejected, but hiding a button is never the control: each route
declares the role it needs.

Rules:

* no session cookie           -> 401
* role not allowed            -> 403
* mutating request without the
  session's CSRF token        -> 403
"""

from __future__ import annotations

import hmac
import logging
from pathlib import Path

from fastapi import Depends, HTTPException, Request, status

from backend.core.config import settings
from backend.services.auth_store import (
    MANAGEMENT_ROLES,
    ROLE_ADMIN,
    SessionUser,
    get_auth_store,
)
from backend.services.document_manager import DocumentManager

logger = logging.getLogger(__name__)

CSRF_HEADER = "X-CSRF-Token"
MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def client_ip(request: Request) -> str | None:
    """Caller address for rate limiting and audit records."""
    if request.client and request.client.host:
        return request.client.host
    return None


def session_token(request: Request) -> str | None:
    return request.cookies.get(settings.session_cookie_name)


def current_session(request: Request) -> SessionUser | None:
    """Resolve the session cookie, or ``None`` for an anonymous caller."""
    token = session_token(request)
    if not token:
        return None
    return get_auth_store().get_session(token)


def require_user(
    request: Request, session: SessionUser | None = Depends(current_session)
) -> SessionUser:
    if session is None:
        _audit_denial(request, "anonymous", "missing session")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in to use document management.",
            headers={"WWW-Authenticate": "Cookie"},
        )
    return session


def _verify_origin(request: Request) -> None:
    """Reject cross-site mutations even if a CSRF token leaked."""
    origin = request.headers.get("origin")
    if not origin:
        return
    host = request.headers.get("host", "")
    if not host:
        return
    origin_host = origin.split("://", 1)[-1].split("/", 1)[0]
    if origin_host != host:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-site requests are not allowed.",
        )


def verify_csrf(request: Request, session: SessionUser) -> None:
    """Double-submit check: the header must match the session's token."""
    if request.method not in MUTATING_METHODS:
        return
    _verify_origin(request)
    supplied = request.headers.get(CSRF_HEADER, "")
    if not supplied or not hmac.compare_digest(supplied, session.csrf_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The request could not be verified. Refresh the page and try again.",
        )


def require_manager(
    request: Request, session: SessionUser = Depends(require_user)
) -> SessionUser:
    """Document management: ADMIN or SOP_MANAGER, plus CSRF on mutations."""
    if session.role not in MANAGEMENT_ROLES:
        _audit_denial(request, session.username, f"role {session.role} cannot manage documents")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role does not allow document management.",
        )
    verify_csrf(request, session)
    return session


def require_admin(
    request: Request, session: SessionUser = Depends(require_user)
) -> SessionUser:
    """Administrator-only operations (accounts, audit log)."""
    if session.role != ROLE_ADMIN:
        _audit_denial(request, session.username, "administrator access required")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access is required.",
        )
    verify_csrf(request, session)
    return session


def _audit_denial(request: Request, username: str, detail: str) -> None:
    """Record refused management access without failing the response."""
    try:
        get_auth_store().audit(
            "unauthorized_access",
            result="failure",
            username=username,
            detail=f"{request.method} {request.url.path}: {detail}",
            ip=client_ip(request),
        )
    except Exception:  # noqa: BLE001 - auditing must not mask the 401/403
        logger.warning("Could not audit a denied management request")


# --- document manager instance ----------------------------------------------

_manager: DocumentManager | None = None
_manager_key: tuple[Path, Path, Path] | None = None


def get_document_manager() -> DocumentManager:
    """Process-wide manager, rebuilt if storage settings change (tests)."""
    global _manager, _manager_key
    key = (
        Path(settings.document_records_path),
        Path(settings.chroma_persist_directory),
        Path(settings.uploads_directory),
    )
    if _manager is None or _manager_key != key:
        _manager = DocumentManager()
        _manager_key = key
    return _manager


def reset_document_manager() -> None:
    global _manager, _manager_key
    _manager = None
    _manager_key = None
