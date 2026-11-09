"""Stage 2 orchestration: discover PDFs, extract pages, chunk text, write JSON.

Run once from the project root:

    python -m backend.services.document_pipeline

Only the three document folders are read; the original PDFs kept in the parent
``Documents`` folder are never modified, moved or deleted.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.core.config import settings
from backend.services.document_models import (
    STATUS_ACTIVE,
    STATUS_ARCHIVED,
    STATUS_SAMPLE_QUESTIONS,
    ProcessedDocument,
    TextChunk,
)
from backend.services.document_registry import DOCUMENT_SPECS, get_spec
from backend.services.pdf_processor import extract_document
from backend.services.text_chunker import chunk_document

logger = logging.getLogger(__name__)


def discover_pdfs(directory: Path) -> list[Path]:
    """Return PDFs directly inside ``directory`` (sorted, non-recursive)."""
    if not directory.is_dir():
        return []
    return sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() == ".pdf"
        ),
        key=lambda path: path.name.lower(),
    )


def run_pipeline() -> dict[str, Any]:
    """Process every document folder once and write the Stage 2 JSON outputs."""
    processed_directory = settings.processed_data_directory
    processed_directory.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    documents: list[ProcessedDocument] = []
    active_chunks: list[TextChunk] = []
    archived_chunks: list[TextChunk] = []
    sample_documents: list[ProcessedDocument] = []

    folders = (
        (settings.active_documents_directory, STATUS_ACTIVE),
        (settings.archived_documents_directory, STATUS_ARCHIVED),
        (settings.sample_questions_directory, STATUS_SAMPLE_QUESTIONS),
    )

    for directory, expected_status in folders:
        for pdf_path in discover_pdfs(directory):
            spec = get_spec(pdf_path.name)
            if spec is None:
                errors.append(
                    f"{pdf_path.name}: not in the verified document registry; "
                    "skipped rather than guessed at"
                )
                continue
            if spec.document_status != expected_status:
                errors.append(
                    f"{pdf_path.name}: registered as '{spec.document_status}' but found "
                    f"in the '{expected_status}' folder; skipped"
                )
                continue

            logger.info("Processing %s", pdf_path.name)
            document = extract_document(pdf_path, spec)
            documents.append(document)
            if document.errors:
                errors.extend(f"{pdf_path.name}: {error}" for error in document.errors)

            if spec.document_status == STATUS_SAMPLE_QUESTIONS:
                # Kept separate from the SOP corpus: extracted, never chunked.
                sample_documents.append(document)
                continue

            chunks = chunk_document(
                document.pages,
                document_code=spec.document_code,
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
            )
            if spec.document_status == STATUS_ARCHIVED:
                archived_chunks.extend(chunks)
            else:
                active_chunks.extend(chunks)

    manifest = _build_manifest(
        documents=documents,
        active_chunks=active_chunks,
        archived_chunks=archived_chunks,
        sample_documents=sample_documents,
        errors=errors,
    )

    outputs = {
        "active_chunks": processed_directory / "active_chunks.json",
        "archived_chunks": processed_directory / "archived_chunks.json",
        "document_manifest": processed_directory / "document_manifest.json",
        "sample_questions_extracted": (
            processed_directory / "sample_questions_extracted.json"
        ),
    }
    # Recorded before the manifest is written so the saved file lists too.
    manifest["outputs"] = {name: str(path) for name, path in outputs.items()}

    _write_json(outputs["active_chunks"], [asdict(chunk) for chunk in active_chunks])
    _write_json(
        outputs["archived_chunks"], [asdict(chunk) for chunk in archived_chunks]
    )
    _write_json(outputs["document_manifest"], manifest)
    _write_json(
        outputs["sample_questions_extracted"],
        [asdict(document) for document in sample_documents],
    )
    return manifest


def _build_manifest(
    *,
    documents: list[ProcessedDocument],
    active_chunks: list[TextChunk],
    archived_chunks: list[TextChunk],
    sample_documents: list[ProcessedDocument],
    errors: list[str],
) -> dict[str, Any]:
    """Assemble the document manifest, including revision supersession data."""
    chunk_counts: dict[str, int] = {}
    for chunk in (*active_chunks, *archived_chunks):
        chunk_counts[chunk.document_id] = chunk_counts.get(chunk.document_id, 0) + 1

    # Active revision per document code - the lookup later stages will use to
    # keep superseded revisions out of retrieval.
    active_revisions = {
        spec.document_code: spec.document_id
        for spec in DOCUMENT_SPECS.values()
        if spec.document_status == STATUS_ACTIVE and spec.document_code
    }

    archived_revisions: list[dict[str, str | None]] = []
    for spec in DOCUMENT_SPECS.values():
        if spec.document_status != STATUS_ARCHIVED:
            continue
        archived_revisions.append(
            {
                "document_id": spec.document_id,
                "document_code": spec.document_code,
                "revision": spec.revision,
                "effective_date": spec.effective_date,
                "superseded_by_document_id": spec.superseded_by_document_id,
            }
        )

    document_entries: list[dict[str, Any]] = []
    for document in documents:
        entry = asdict(document.metadata)
        entry["chunk_count"] = chunk_counts.get(document.metadata.document_id, 0)
        entry["chunked"] = document.metadata.document_status != STATUS_SAMPLE_QUESTIONS
        entry["pages_with_text"] = sum(1 for page in document.pages if page.page_text)
        document_entries.append(entry)

    warnings = [
        f"{document.metadata.source_filename}: {warning}"
        for document in documents
        for warning in document.metadata.extraction_warnings
    ]

    summary = {
        "active_documents": sum(
            1 for doc in documents if doc.metadata.document_status == STATUS_ACTIVE
        ),
        "archived_documents": sum(
            1 for doc in documents if doc.metadata.document_status == STATUS_ARCHIVED
        ),
        "sample_question_documents": len(sample_documents),
        "documents_total": len(documents),
        "pages_extracted": sum(len(doc.pages) for doc in documents),
        "active_chunks": len(active_chunks),
        "archived_chunks": len(archived_chunks),
        "extraction_warnings": len(warnings),
        "errors": len(errors),
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stage": 2,
        "chunking": {
            "chunk_size": settings.chunk_size,
            "chunk_overlap": settings.chunk_overlap,
            "unit": "characters",
            "chunks_cross_pages": False,
        },
        "active_revisions": active_revisions,
        "archived_revisions": archived_revisions,
        "documents": document_entries,
        "summary": summary,
        "warnings": warnings,
        "errors": errors,
    }


def _write_json(path: Path, payload: Any) -> None:
    """Write ``payload`` as UTF-8 JSON with a trailing newline."""
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> int:
    """Run the pipeline once and print a short summary."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    manifest = run_pipeline()
    print(json.dumps(manifest["summary"], indent=2, ensure_ascii=False))

    if manifest["warnings"]:
        print("\nExtraction warnings:")
        for warning in manifest["warnings"]:
            print(f" - {warning}")

    if manifest["errors"]:
        print("\nErrors:")
        for error in manifest["errors"]:
            print(f" - {error}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
