"""Authentication, session and account-management endpoints.

Security notes:

* Passwords are compared against PBKDF2 hashes; the plaintext never leaves the
  request body and is never logged.
* The session cookie is HttpOnly, SameSite=Lax, and Secure when the request is
  served over HTTPS (or when SESSION_COOKIE_SECURE=true).
* Mutating routes require the session's CSRF token in ``X-CSRF-Token``.
* Repeated failures for the same username or IP are refused with HTTP 429 until
  the window passes; every attempt is audited.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from backend.api.deps import (
    MUTATING_METHODS,
    client_ip,
    current_session,
    require_admin,
    require_user,
    session_token,
    verify_csrf,
)
from backend.core.config import settings
from backend.core.security import password_problem, verify_password
from backend.services.auth_store import (
    ROLES,
    AuthError,
    ROLE_ADMIN,
    SessionUser,
    get_auth_store,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["authentication"])
admin_router = APIRouter(prefix="/api", tags=["accounts"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=256)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=256)
    new_password: str = Field(..., min_length=1, max_length=256)


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=256)
    role: str = Field(..., max_length=32)
    full_name: str = Field("", max_length=120)


class UserUpdateRequest(BaseModel):
    role: str | None = Field(None, max_length=32)
    is_active: bool | None = None
    password: str | None = Field(None, max_length=256)
    full_name: str | None = Field(None, max_length=120)


def _cookie_secure(request: Request) -> bool:
    setting = str(settings.session_cookie_secure).strip().lower()
    if setting in {"1", "true", "yes", "on"}:
        return True
    if setting in {"0", "false", "no", "off"}:
        return False
    forwarded = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
    return request.url.scheme == "https" or forwarded == "https"


def _set_session_cookie(response: Response, request: Request, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=max(60, settings.session_ttl_hours * 3600),
        httponly=True,
        secure=_cookie_secure(request),
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name, path="/", httponly=True, samesite="lax"
    )


def _session_payload(session: SessionUser) -> dict[str, Any]:
    return {
        "authenticated": True,
        "user": session.as_dict(),
        "csrf_token": session.csrf_token,
        "expires_at": session.expires_at,
    }


@router.post("/login", summary="Sign in")
def login(
    payload: LoginRequest, request: Request, response: Response
) -> dict[str, Any]:
    """Authenticate a manager or employee and start a session."""
    store = get_auth_store()
    ip = client_ip(request)
    username = payload.username.strip()

    if store.user_count() == 0:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "No accounts exist yet. Set INITIAL_ADMIN_USERNAME and "
                "INITIAL_ADMIN_PASSWORD in .env and restart, or run "
                "'python -m backend.services.auth_store create-admin --username <name>'."
            ),
        )

    account_failures = store.recent_login_failures(username=username)
    address_failures = store.recent_ip_failures(ip=ip)
    if (
        account_failures >= settings.login_max_attempts
        or address_failures >= settings.login_ip_max_attempts
    ):
        store.audit(
            "login_blocked",
            result="failure",
            username=username,
            detail=(
                f"rate limit ({account_failures} failures for this account, "
                f"{address_failures} from this address in "
                f"{settings.login_window_minutes} minutes)"
            ),
            ip=ip,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Too many failed sign-in attempts. Wait "
                f"{settings.login_window_minutes} minutes and try again."
            ),
        )

    user = store.verify_credentials(username, payload.password)
    if user is None or not user.is_active:
        store.audit(
            "login_failed",
            result="failure",
            username=username,
            detail="invalid credentials",
            ip=ip,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
        )

    token, session = store.create_session(user, ip=ip)
    store.mark_login(user.id)
    store.audit(
        "login_success",
        result="success",
        username=user.username,
        user_id=user.id,
        detail=f"role {user.role}",
        ip=ip,
    )
    _set_session_cookie(response, request, token)
    return _session_payload(session)


@router.post("/logout", summary="Sign out")
def logout(
    request: Request,
    response: Response,
    session: SessionUser = Depends(require_user),
) -> dict[str, Any]:
    """End the current session and clear the cookie."""
    if request.method in MUTATING_METHODS:
        verify_csrf(request, session)
    store = get_auth_store()
    token = session_token(request)
    if token:
        store.delete_session(token)
    store.audit(
        "logout",
        result="success",
        username=session.username,
        user_id=session.user_id,
        ip=client_ip(request),
    )
    _clear_session_cookie(response)
    return {"authenticated": False}


@router.get("/me", summary="Current session")
def me(request: Request) -> dict[str, Any]:
    """Report the caller's session, without requiring one."""
    session = current_session(request)
    if session is None:
        return {"authenticated": False, "user": None, "csrf_token": None}
    return _session_payload(session)


@router.post("/change-password", summary="Change your own password")
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    session: SessionUser = Depends(require_user),
) -> dict[str, Any]:
    """Change the signed-in user's password and end all their sessions."""
    verify_csrf(request, session)
    store = get_auth_store()
    user = store.get_user(session.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="The account no longer exists.")

    with_hash = store.verify_credentials(user.username, payload.current_password)
    if with_hash is None:
        store.audit(
            "password_change_failed",
            result="failure",
            username=user.username,
            user_id=user.id,
            detail="current password incorrect",
            ip=client_ip(request),
        )
        raise HTTPException(status_code=400, detail="The current password is incorrect.")

    problem = password_problem(payload.new_password)
    if problem:
        raise HTTPException(status_code=422, detail=problem)

    store.update_user(user.id, password=payload.new_password)
    store.audit(
        "password_changed",
        result="success",
        username=user.username,
        user_id=user.id,
        ip=client_ip(request),
    )
    _clear_session_cookie(response)
    return {"changed": True, "message": "Password changed. Sign in again."}


@admin_router.get("/users", summary="List accounts (administrator)")
def list_users(session: SessionUser = Depends(require_admin)) -> dict[str, Any]:
    users = [user.as_dict() for user in get_auth_store().list_users()]
    return {"users": users, "roles": list(ROLES)}


@admin_router.post("/users", status_code=201, summary="Create an account (administrator)")
def create_user(
    payload: UserCreateRequest,
    request: Request,
    session: SessionUser = Depends(require_admin),
) -> dict[str, Any]:
    store = get_auth_store()
    try:
        user = store.create_user(
            payload.username, payload.password, payload.role, full_name=payload.full_name
        )
    except AuthError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    store.audit(
        "user_created",
        result="success",
        username=session.username,
        user_id=session.user_id,
        detail=f"created {user.username} as {user.role}",
        ip=client_ip(request),
    )
    return {"user": user.as_dict()}


@admin_router.patch("/users/{user_id}", summary="Update an account (administrator)")
def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    request: Request,
    session: SessionUser = Depends(require_admin),
) -> dict[str, Any]:
    store = get_auth_store()
    target = store.get_user(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Account not found.")

    if target.role == ROLE_ADMIN and (
        (payload.role is not None and payload.role != ROLE_ADMIN)
        or payload.is_active is False
    ):
        active_admins = sum(
            1 for user in store.list_users() if user.role == ROLE_ADMIN and user.is_active
        )
        if target.is_active and active_admins <= 1:
            raise HTTPException(
                status_code=409,
                detail="This is the last active administrator; promote another account first.",
            )

    try:
        updated = store.update_user(
            user_id,
            role=payload.role,
            is_active=payload.is_active,
            password=payload.password,
            full_name=payload.full_name,
        )
    except AuthError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    changes = ", ".join(
        name
        for name, value in (
            ("role", payload.role),
            ("active", payload.is_active),
            ("password", payload.password),
            ("full_name", payload.full_name),
        )
        if value is not None
    )
    store.audit(
        "user_updated",
        result="success",
        username=session.username,
        user_id=session.user_id,
        detail=f"{updated.username}: {changes or 'no changes'}",
        ip=client_ip(request),
    )
    return {"user": updated.as_dict()}


@admin_router.get("/audit", summary="Recent audit records (administrator)")
def audit_log(
    limit: int = 100, offset: int = 0, session: SessionUser = Depends(require_admin)
) -> dict[str, Any]:
    records = get_auth_store().list_audit(limit=limit, offset=offset)
    return {"records": records, "count": len(records), "limit": limit, "offset": offset}
