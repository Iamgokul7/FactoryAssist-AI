"""Grounded chat endpoint backed by the RAG service."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from backend.core.config import settings
from backend.services.rag_service import RagService

router = APIRouter(prefix="/api", tags=["chat"])

_service = RagService()

ChatStatus = Literal[
    "answered",
    "insufficient_evidence",
    "not_configured",
    "error",
    "invalid_question",
]


class ChatRequest(BaseModel):
    """A supervisor's question."""

    question: str = Field(
        ...,
        description="Question about the manufacturing SOPs or manuals.",
        max_length=settings.max_question_length * 2,
    )


class SourceModel(BaseModel):
    """A document location cited by the answer."""

    document_id: str
    document_title: str
    document_code: str
    revision: str
    page_number: int
    source_filename: str
    similarity: float


class ChatResponse(BaseModel):
    """Structured answer with citations and a machine-readable status."""

    status: ChatStatus
    answer: str
    sources: list[SourceModel]
    grounded: bool
    detail: str | None = None


@router.post("/chat", response_model=ChatResponse, summary="Ask a question")
async def chat(payload: ChatRequest) -> ChatResponse:
    """Answer a question from the active manufacturing documents only."""
    question = " ".join(payload.question.split())
    if not question:
        raise HTTPException(status_code=400, detail="Please enter a question.")

    # The Gen AI SDK is synchronous; keep the event loop free.
    result = await run_in_threadpool(_service.answer_question, question)

    return ChatResponse(
        status=result.status,  # type: ignore[arg-type]
        answer=result.answer,
        sources=[SourceModel(**source.as_dict()) for source in result.sources],
        grounded=result.grounded,
        detail=result.detail,
    )
