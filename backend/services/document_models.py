"""Data models shared by the Stage 2 document-processing pipeline.

Plain dataclasses are used deliberately: they are easy to serialise with
``dataclasses.asdict`` and avoid pulling in extra abstraction for what is a
straightforward extract-then-chunk flow.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Document status values. ``sample_questions`` is kept separate from the SOP
# corpus on purpose: it is assignment test material, not a plant procedure.
STATUS_ACTIVE = "active"
STATUS_ARCHIVED = "archived"
STATUS_SAMPLE_QUESTIONS = "sample_questions"


@dataclass(slots=True)
class DocumentSpec:
    """Verified identity of a document, taken from the PDF itself."""

    document_id: str
    document_title: str
    document_code: str
    revision: str
    document_type: str
    source_filename: str
    document_status: str
    effective_date: str | None = None
    supersedes_document_id: str | None = None
    superseded_by_document_id: str | None = None


@dataclass(slots=True)
class DocumentMetadata:
    """Document-level metadata recorded for every processed PDF."""

    document_id: str
    document_title: str
    document_code: str
    revision: str
    document_type: str
    source_filename: str
    source_path: str
    document_status: str
    page_count: int
    extraction_timestamp: str
    effective_date: str | None = None
    supersedes_document_id: str | None = None
    superseded_by_document_id: str | None = None
    extraction_warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ExtractedPage:
    """Text extracted from a single PDF page (page numbers start at 1)."""

    document_id: str
    document_title: str
    revision: str
    page_number: int
    page_text: str
    document_status: str
    source_filename: str


@dataclass(slots=True)
class ProcessedDocument:
    """A processed document: metadata, its pages and any extraction errors."""

    metadata: DocumentMetadata
    pages: list[ExtractedPage] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TextChunk:
    """A retrievable slice of one page, carrying its full document identity."""

    chunk_id: str
    document_id: str
    document_title: str
    document_code: str
    revision: str
    document_status: str
    source_filename: str
    page_number: int
    page_range: str
    chunk_index: int
    char_count: int
    chunk_text: str
