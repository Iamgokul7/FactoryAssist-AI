"""FactoryAssist AI - FastAPI application entry point.

Serves the JSON API and the single-page dashboard from the same origin, so no
separate frontend server is required:

    uvicorn backend.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api import chat, health
from backend.core.config import settings

app = FastAPI(
    title=settings.app_name,
    description=(
        "AI-powered manufacturing SOP copilot. Answers are grounded in the "
        "plant's active SOP and maintenance documents, with page-level citations."
    ),
    version=settings.app_version,
    debug=settings.debug,
)

app.include_router(health.router)
app.include_router(chat.router)

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
        "stage": 6,
        "version": settings.app_version,
        "dashboard": "open this URL in a browser",
        "api_status": "/api/status",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.server_host,
        port=settings.server_port,
    )
