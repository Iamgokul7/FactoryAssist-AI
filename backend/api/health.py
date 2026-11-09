"""Health and system-status endpoints.

The status payload is what the dashboard uses, so it reports real state:
whether Gemini is configured, whether the vector index is reachable, and which
revision of each document is active. It never exposes credentials.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from backend.core.config import settings
from backend.services import knowledge_base
from backend.services.vector_store import VectorStore, VectorStoreError

router = APIRouter(tags=["system"])


@router.get("/health", summary="Health check")
async def health() -> dict[str, Any]:
    """Liveness probe used by the dashboard and by manual checks."""
    return {"status": "healthy"}


@router.get("/api/status", summary="Application and corpus status")
async def application_status() -> dict[str, Any]:
    """Report service availability, models and corpus statistics."""
    summary = knowledge_base.corpus_summary()
    documents = knowledge_base.documents()

    chroma_available = True
    indexed_chunks = 0
    vector_detail: str | None = None
    try:
        indexed_chunks = VectorStore().count()
    except VectorStoreError as exc:
        chroma_available = False
        vector_detail = str(exc)

    return {
        "application": settings.app_name,
        "version": settings.app_version,
        "stage": 6,
        "status": "running",
        "gemini": {
            "configured": settings.is_gemini_configured,
            "generation_model": settings.gemini_model,
            "embedding_model": settings.gemini_embedding_model,
        },
        "vector_store": {
            "available": chroma_available,
            "collection": settings.chroma_active_collection,
            "indexed_chunks": indexed_chunks,
            "detail": vector_detail,
        },
        "corpus": {
            **summary,
            "active_documents": [
                doc for doc in documents if doc.get("document_status") == "active"
            ],
            "archived_documents": [
                doc for doc in documents if doc.get("document_status") == "archived"
            ],
        },
        "retrieval": {
            "top_k": settings.retrieval_top_k,
            "min_similarity": settings.retrieval_min_similarity,
        },
        "index_ready": indexed_chunks > 0,
    }
