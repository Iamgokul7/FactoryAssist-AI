"""FactoryAssist AI - FastAPI application entry point (Stage 1).

Only the application skeleton and the two system endpoints exist at this
stage. Chat, PDF upload, RAG and Gemini integration are added in later stages.
"""

from fastapi import FastAPI

from backend.core.config import settings

app = FastAPI(
    title=settings.app_name,
    description="AI-powered manufacturing SOP copilot for supervisors.",
    version=settings.app_version,
    debug=settings.debug,
)


@app.get("/", tags=["system"])
async def root() -> dict[str, str | int]:
    """Basic landing endpoint confirming the service is up."""
    return {
        "application": settings.app_name,
        "status": "running",
        "stage": 1,
    }


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.server_host,
        port=settings.server_port,
    )
