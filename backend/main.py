"""FactoryAssist AI - FastAPI application entry point.

Serves the JSON API and the single-page dashboard from the same origin, so no
separate frontend server is required:

    uvicorn backend.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api import auth, chat, documents, health
from backend.core.config import settings
from backend.services.auth_store import ensure_initial_admin, get_auth_store
from backend.services.document_manager import recover_interrupted_processing

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Prepare access control and recover interrupted work at startup.

    A failure here is logged rather than fatal: the assistant must keep working
    even if the management database cannot be opened, while every management
    route will then fail closed with a 401.
    """
    try:
        settings.managed_data_directory.mkdir(parents=True, exist_ok=True)
        settings.uploads_directory.mkdir(parents=True, exist_ok=True)
        store = get_auth_store()
        ensure_initial_admin()
        store.purge_expired_sessions()
        recover_interrupted_processing()
    except Exception as exc:  # noqa: BLE001 - the chatbot must still start
        logger.error("Management setup failed: %s", type(exc).__name__)
    yield


app = FastAPI(
    title=settings.app_name,
    description=(
        "AI-powered manufacturing SOP copilot. Answers are grounded in the "
        "plant's active SOP and maintenance documents, with page-level citations. "
        "Document management requires an authenticated administrator or SOP manager."
    ),
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(auth.router)
app.include_router(auth.admin_router)
app.include_router(documents.router)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Conservative response headers for a locally hosted management UI."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
    )
    if request.url.path.startswith("/api/"):
        # Session-scoped data and document metadata must not be cached by
        # shared proxies or the browser's back/forward cache.
        response.headers.setdefault("Cache-Control", "no-store")
    if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    return response

# Static assets for the dashboard (CSS/JS).
_frontend_directory = settings.frontend_directory
if _frontend_directory.is_dir():
    app.mount(
        "/static",
        StaticFiles(directory=str(_frontend_directory)),
        name="static",
    )


@app.get("/", tags=["system"], summary="Application information or dashboard")
async def root(request: Request):
    """Return application info to API clients, or the dashboard to browsers."""
    index_file = _frontend_directory / "index.html"
    if "text/html" in request.headers.get("accept", "") and index_file.is_file():
        return FileResponse(index_file)

    return {
        "application": settings.app_name,
        "status": "running",
        "stage": 7,
        "version": settings.app_version,
        "dashboard": "open this URL in a browser",
        "api_status": "/api/status",
        "document_management": "/api/documents",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.server_host,
        port=settings.server_port,
    )
