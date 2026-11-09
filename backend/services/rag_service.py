"""Retrieval-augmented answer generation for FactoryAssist AI.

Flow: embed the question -> search the active ChromaDB collection -> filter by
relevance and by active revision -> ask Gemini to answer strictly from the
retrieved evidence -> return the answer with the sources it actually used.

Archived revisions are never retrieved, and citations are built only from
chunks that were retrieved and passed to the model.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Sequence

from google import genai
from google.genai import types

from backend.core.config import settings
from backend.services.embedding_service import EmbeddingError, EmbeddingService
from backend.services.gemini_client import (
    GeminiNotConfiguredError,
    GeminiRequestError,
    create_client,
    describe_error,
    is_retryable,
)
from backend.services.knowledge_base import active_revisions
from backend.services.vector_store import RetrievedChunk, VectorStore, VectorStoreError

logger = logging.getLogger(__name__)

STATUS_ANSWERED = "answered"
STATUS_INSUFFICIENT = "insufficient_evidence"
STATUS_NOT_CONFIGURED = "not_configured"
STATUS_ERROR = "error"
STATUS_INVALID = "invalid_question"

FALLBACK_ANSWER = (
    "I couldn't find sufficient information to answer this question in the "
    "available manufacturing documents. Please consult the relevant SOP or "
    "contact the responsible supervisor."
)

_MAX_ATTEMPTS = 2
_BACKOFF_SECONDS = 2.0

SYSTEM_INSTRUCTION = f"""You are FactoryAssist AI, a document-grounded copilot for \
manufacturing shop-floor supervisors at Kaveri Precision Components.

You answer ONLY from the EVIDENCE section of the user message. The evidence \
contains extracts from the plant's controlled SOPs and manuals.

Non-negotiable rules:
1. Use only facts stated in the evidence. Never fill gaps with general \
knowledge, industry-typical values or assumptions.
2. Never invent or alter values, tolerances, units, alarm codes, document \
numbers, revisions, page numbers or step sequences. Reproduce them exactly as \
written.
3. Never invent a procedure or a safety instruction that is not in the evidence.
4. If the evidence does not clearly answer the question, or answers only part \
of it, set "supported" to false.
5. When "supported" is false, the answer must be exactly this sentence: \
"{FALLBACK_ANSWER}"
6. Never mention "evidence", "chunks", "context" or source numbers in the answer.
7. Be concise and practical for a supervisor on the shop floor: short \
sentences or short numbered steps. Mention the document code and revision when \
it helps the reader verify the instruction.
8. If two documents give conflicting values, state both and name the documents.
9. Answer in the language of the question.

Return JSON only, with these fields:
- "answer": string - the answer for the supervisor.
- "supported": boolean - true only when the evidence fully supports the answer.
- "used_source_indices": array of integers - the 1-based evidence numbers you \
actually used. Use an empty array when "supported" is false."""

_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "supported": {"type": "boolean"},
        "used_source_indices": {"type": "array", "items": {"type": "integer"}},
    },
    "required": ["answer", "supported", "used_source_indices"],
}


@dataclass(slots=True)
class SourceReference:
    """A document location a grounded answer is based on."""

    document_id: str
    document_title: str
    document_code: str
    revision: str
    page_number: int
    source_filename: str
    similarity: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "document_title": self.document_title,
            "document_code": self.document_code,
            "revision": self.revision,
            "page_number": self.page_number,
            "source_filename": self.source_filename,
            "similarity": round(self.similarity, 3),
        }


@dataclass(slots=True)
class RagAnswer:
    """Result of one question, shaped for the API layer."""

    status: str
    answer: str
    sources: list[SourceReference] = field(default_factory=list)
    grounded: bool = False
    detail: str | None = None


class RagService:
    """Retrieval and grounded generation, using the active document index."""

    def __init__(
        self,
        *,
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStore | None = None,
        client: genai.Client | None = None,
    ) -> None:
        self._embeddings = embedding_service or EmbeddingService()
        self._store = vector_store or VectorStore()
        self._client = client

    # --- public API ---

    def answer_question(self, question: str) -> RagAnswer:
        """Answer ``question`` from the active manufacturing documents."""
        question = " ".join((question or "").split())
        if not question:
            return RagAnswer(
                status=STATUS_INVALID,
                answer="Please enter a question about the manufacturing documents.",
                detail="The question was empty.",
            )
        if len(question) > settings.max_question_length:
            return RagAnswer(
                status=STATUS_INVALID,
                answer=(
                    "That question is too long. Please keep it under "
                    f"{settings.max_question_length} characters."
                ),
                detail="question_too_long",
            )
        if not settings.is_gemini_configured:
            return _not_configured()

        try:
            query_vector = self._embeddings.embed_query(question)
        except GeminiNotConfiguredError:
            return _not_configured()
        except EmbeddingError as exc:
            logger.warning("Query embedding failed: %s", type(exc).__name__)
            return RagAnswer(
                status=STATUS_ERROR,
                answer="I couldn't search the documents just now. Please try again.",
                detail=str(exc),
            )

        try:
            candidates = self._store.query(
                query_vector,
                top_k=settings.retrieval_top_k,
                where={"document_status": "active"},
            )
        except VectorStoreError as exc:
            return RagAnswer(
                status=STATUS_ERROR,
                answer=(
                    "The document index is not available. Run "
                    "'python -m backend.services.ingestion_service' and try again."
                ),
                detail=str(exc),
            )

        if not candidates:
            return RagAnswer(
                status=STATUS_ERROR,
                answer=(
                    "The document index is empty. Run "
                    "'python -m backend.services.ingestion_service' to index the "
                    "manufacturing documents, then ask again."
                ),
                detail="index_empty",
            )

        relevant = self._keep_active(
            [chunk for chunk in candidates if chunk.similarity >= settings.retrieval_min_similarity]
        )
        if not relevant:
            best = max(chunk.similarity for chunk in candidates)
            return RagAnswer(
                status=STATUS_INSUFFICIENT,
                answer=FALLBACK_ANSWER,
                detail=f"no_relevant_evidence (best similarity {best:.2f})",
            )

        try:
            answer_text, supported, used_indices = self._generate(question, relevant)
        except GeminiNotConfiguredError:
            return _not_configured()
        except GeminiRequestError as exc:
            logger.warning("Answer generation failed: %s", type(exc).__name__)
            return RagAnswer(
                status=STATUS_ERROR,
                answer="The AI service is temporarily unavailable. Please try again.",
                detail=str(exc),
            )

        answer_text = answer_text.strip()
        if (
            not supported
            or not answer_text
            or answer_text.lower().startswith("i couldn't find sufficient information")
        ):
            return RagAnswer(
                status=STATUS_INSUFFICIENT,
                answer=FALLBACK_ANSWER,
                detail="model_reported_insufficient_evidence",
            )

        return RagAnswer(
            status=STATUS_ANSWERED,
            answer=answer_text,
            sources=_sources_for(relevant, used_indices),
            grounded=True,
        )

    # --- internals ---

    def _keep_active(self, chunks: Sequence[RetrievedChunk]) -> list[RetrievedChunk]:
        """Defence in depth: drop anything not from the active revision."""
        revisions = active_revisions()
        kept: list[RetrievedChunk] = []
        for chunk in chunks:
            if chunk.document_status != "active":
                logger.warning(
                    "Dropping %s: status is %s", chunk.chunk_id, chunk.document_status
                )
                continue
            expected = revisions.get(chunk.document_code)
            if expected and expected != chunk.document_id:
                logger.warning(
                    "Dropping %s: revision %s of %s is not active",
                    chunk.chunk_id,
                    chunk.revision,
                    chunk.document_code,
                )
                continue
            kept.append(chunk)
        return kept

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = create_client()
        return self._client

    def _generate(
        self, question: str, chunks: Sequence[RetrievedChunk]
    ) -> tuple[str, bool, list[int]]:
        prompt = _build_prompt(question, chunks)
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=settings.gemini_temperature,
            max_output_tokens=settings.gemini_max_output_tokens,
            response_mime_type="application/json",
            response_schema=_RESPONSE_SCHEMA,
            # Answers are short and evidence-bound; thinking tokens would only
            # add latency and risk truncating the JSON reply.
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )

        last_error: Exception | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = self._get_client().models.generate_content(
                    model=settings.gemini_model, contents=prompt, config=config
                )
                return _parse_response(response, source_count=len(chunks))
            except GeminiNotConfiguredError:
                raise
            except Exception as exc:  # noqa: BLE001 - normalised below
                last_error = exc
                if attempt == _MAX_ATTEMPTS or not is_retryable(exc):
                    break
                time.sleep(_BACKOFF_SECONDS * attempt)

        message = describe_error(last_error) if last_error else "Generation failed"
        raise GeminiRequestError(message) from last_error


def _not_configured() -> RagAnswer:
    return RagAnswer(
        status=STATUS_NOT_CONFIGURED,
        answer=(
            "The AI service is not configured yet. Add your Gemini API key to the "
            ".env file in the project root and restart the application. The "
            "documents are processed and ready to be indexed once the key is set."
        ),
        detail="GEMINI_API_KEY is missing from .env",
    )


def _build_prompt(question: str, chunks: Sequence[RetrievedChunk]) -> str:
    """Assemble the question and numbered evidence blocks."""
    blocks: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        blocks.append(
            f"[{index}] {chunk.document_title}\n"
            f"Code: {chunk.document_code} | Revision: {chunk.revision} | "
            f"Page: {chunk.page_number} | File: {chunk.source_filename}\n"
            f"Text:\n{chunk.text}"
        )

    return (
        f"QUESTION\n{question}\n\n"
        "EVIDENCE\n"
        + "\n\n".join(blocks)
        + "\n\nAnswer the question using only the evidence above."
    )


def _parse_response(
    response: Any, *, source_count: int
) -> tuple[str, bool, list[int]]:
    """Read the model's JSON reply, tolerating a plain-text fallback."""
    payload: Any = getattr(response, "parsed", None)

    if payload is None:
        text = ""
        try:
            text = (response.text or "").strip()
        except Exception:  # noqa: BLE001 - blocked/empty responses
            text = ""
        payload = _load_json(text) or {
            "answer": text,
            "supported": bool(text),
            "used_source_indices": [],
        }

    if not isinstance(payload, dict):
        return str(payload), True, []

    answer = str(payload.get("answer") or "").strip()
    supported = bool(payload.get("supported"))
    raw_indices = payload.get("used_source_indices") or []

    indices: list[int] = []
    for value in raw_indices:
        try:
            index = int(value)
        except (TypeError, ValueError):
            continue
        if 1 <= index <= source_count and index not in indices:
            indices.append(index)

    return answer, supported, indices


def _load_json(text: str) -> dict[str, Any] | None:
    """Parse JSON, optionally wrapped in a Markdown code fence."""
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned[: -len("```")]
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _sources_for(
    chunks: Sequence[RetrievedChunk], used_indices: Sequence[int]
) -> list[SourceReference]:
    """Build unique source references for the evidence actually used."""
    if used_indices:
        selected = [chunks[index - 1] for index in used_indices]
    else:
        # The model did not name indices; every retrieved chunk was its evidence.
        selected = list(chunks)

    sources: list[SourceReference] = []
    seen: set[tuple[str, int]] = set()
    for chunk in selected:
        key = (chunk.document_id, chunk.page_number)
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            SourceReference(
                document_id=chunk.document_id,
                document_title=chunk.document_title,
                document_code=chunk.document_code,
                revision=chunk.revision,
                page_number=chunk.page_number,
                source_filename=chunk.source_filename,
                similarity=chunk.similarity,
            )
        )
    return sources
