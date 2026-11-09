"""Page-by-page PDF text extraction for FactoryAssist AI (Stage 2).

PyMuPDF is used strictly for text extraction. No OCR is performed, and no
content is invented for pages that carry no extractable text: such pages are
recorded as extraction warnings and left empty.

Extraction problems are recorded on the returned :class:`ProcessedDocument`
instead of being raised, so a single damaged PDF cannot abort a whole run.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import pymupdf

from backend.services.document_models import (
    DocumentMetadata,
    DocumentSpec,
    ExtractedPage,
    ProcessedDocument,
)

logger = logging.getLogger(__name__)


def extract_document(pdf_path: Path, spec: DocumentSpec) -> ProcessedDocument:
    """Extract ``pdf_path`` page by page into a :class:`ProcessedDocument`."""
    metadata = DocumentMetadata(
        document_id=spec.document_id,
        document_title=spec.document_title,
        document_code=spec.document_code,
        revision=spec.revision,
        document_type=spec.document_type,
        source_filename=spec.source_filename,
        source_path=str(pdf_path),
        document_status=spec.document_status,
        page_count=0,
        extraction_timestamp=_utc_now(),
        effective_date=spec.effective_date,
        supersedes_document_id=spec.supersedes_document_id,
        superseded_by_document_id=spec.superseded_by_document_id,
    )
    result = ProcessedDocument(metadata=metadata)

    try:
        with pymupdf.open(pdf_path) as document:
            if document.needs_pass:
                result.errors.append("PDF is password protected and cannot be read")
                return result

            metadata.page_count = document.page_count
            if metadata.page_count == 0:
                result.errors.append("PDF contains no pages")
                return result

            for page_number, page in enumerate(document, start=1):
                result.pages.append(_extract_page(page, page_number, spec, metadata))
    except Exception as exc:  # noqa: BLE001 - a broken PDF must not stop the run
        logger.error("Failed to extract %s: %s", pdf_path.name, exc)
        result.errors.append(f"could not read PDF: {exc}")
        return result

    _verify_document_identity(spec, metadata, result)
    return result


def _extract_page(
    page: pymupdf.Page,
    page_number: int,
    spec: DocumentSpec,
    metadata: DocumentMetadata,
) -> ExtractedPage:
    """Extract one page, normalising whitespace and flagging empty pages."""
    raw_text = ""
    try:
        raw_text = page.get_text("text") or ""
    except Exception as exc:  # noqa: BLE001 - keep processing the other pages
        metadata.extraction_warnings.append(
            f"page {page_number}: text extraction failed ({exc})"
        )

    page_text = _normalise_text(raw_text)
    if not page_text:
        metadata.extraction_warnings.append(
            f"page {page_number}: no extractable text (scanned or image-only page); "
            "content left empty rather than invented"
        )

    return ExtractedPage(
        document_id=spec.document_id,
        document_title=spec.document_title,
        revision=spec.revision,
        page_number=page_number,
        page_text=page_text,
        document_status=spec.document_status,
        source_filename=spec.source_filename,
    )


def _normalise_text(text: str) -> str:
    """Normalise line endings and collapse runs of blank lines."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _verify_document_identity(
    spec: DocumentSpec,
    metadata: DocumentMetadata,
    result: ProcessedDocument,
) -> None:
    """Cross-check the registry entry against what page 1 actually prints.

    This catches a mis-filed or replaced PDF instead of letting wrong metadata
    flow into the corpus.
    """
    if not result.pages:
        return

    first_page = result.pages[0].page_text
    if not first_page:
        metadata.extraction_warnings.append(
            "page 1 has no text, so the document identity could not be verified"
        )
        return

    haystack = first_page.lower()

    if spec.document_code and spec.document_code.lower() not in haystack:
        metadata.extraction_warnings.append(
            f"document code {spec.document_code} not found on page 1"
        )

    if spec.revision and not re.search(
        rf"\brev(?:ision)?\s*0*{re.escape(spec.revision)}\b", haystack
    ):
        metadata.extraction_warnings.append(
            f"revision {spec.revision} not found on page 1"
        )

    if spec.effective_date and spec.effective_date.lower() not in haystack:
        metadata.extraction_warnings.append(
            f"effective date {spec.effective_date} not found on page 1"
        )


def _utc_now() -> str:
    """Current UTC timestamp in ISO 8601 form."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
