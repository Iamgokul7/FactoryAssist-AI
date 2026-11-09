"""Verified catalogue of the manufacturing documents used in this project.

Every field below was read from the PDF itself (document number, revision,
title and effective date printed on page 1), not inferred from the filename.
Anything not listed here is refused by the pipeline instead of being guessed
at.

Revision handling: QC-SOP-014 Rev 04 supersedes Rev 03. Rev 04 is ``active``
and belongs to the knowledge corpus; Rev 03 is ``archived`` and is kept for
historical reference only, so its content is never mixed into active chunks.
"""

from __future__ import annotations

from backend.services.document_models import (
    STATUS_ACTIVE,
    STATUS_ARCHIVED,
    STATUS_SAMPLE_QUESTIONS,
    DocumentSpec,
)

QC_SOP_014_REV03 = DocumentSpec(
    document_id="qc-sop-014-rev03",
    document_title="Incoming Material Inspection - Standard Operating Procedure",
    document_code="QC-SOP-014",
    revision="03",
    document_type="quality_procedure",
    source_filename="QC-SOP-014_Rev03_Incoming_Material_Inspection.pdf",
    document_status=STATUS_ARCHIVED,
    effective_date="15-Mar-2023",
    superseded_by_document_id="qc-sop-014-rev04",
)

QC_SOP_014_REV04 = DocumentSpec(
    document_id="qc-sop-014-rev04",
    document_title="Incoming Material Inspection - Standard Operating Procedure",
    document_code="QC-SOP-014",
    revision="04",
    document_type="quality_procedure",
    source_filename="QC-SOP-014_Rev04_Incoming_Material_Inspection.pdf",
    document_status=STATUS_ACTIVE,
    effective_date="01-Jul-2026",
    supersedes_document_id="qc-sop-014-rev03",
)

SAF_SOP_003_REV05 = DocumentSpec(
    document_id="saf-sop-003-rev05",
    document_title="Lockout / Tagout (LOTO) - Safety Procedure",
    document_code="SAF-SOP-003",
    revision="05",
    document_type="safety_procedure",
    source_filename="SAF-SOP-003_Lockout_Tagout_Procedure.pdf",
    document_status=STATUS_ACTIVE,
    effective_date="12-Feb-2026",
)

MNT_MAN_CNC_02_REV02 = DocumentSpec(
    document_id="mnt-man-cnc-02-rev02",
    document_title="Preventive Maintenance Manual - TX-200 CNC Turning Centre",
    document_code="MNT-MAN-CNC-02",
    revision="02",
    document_type="maintenance_manual",
    source_filename="MNT-MAN-CNC-02_TX-200_Preventive_Maintenance.pdf",
    document_status=STATUS_ACTIVE,
    effective_date="20-Jan-2026",
)

SAMPLE_QUESTIONS = DocumentSpec(
    document_id="sample-questions",
    # No document code or revision is printed on this sheet, so none is invented.
    document_title="BiztelAI - Assignment Sample Questions",
    document_code="",
    revision="",
    document_type="sample_questions",
    source_filename="Sample_Questions.pdf",
    document_status=STATUS_SAMPLE_QUESTIONS,
    effective_date=None,
)

DOCUMENT_SPECS: dict[str, DocumentSpec] = {
    spec.source_filename: spec
    for spec in (
        QC_SOP_014_REV03,
        QC_SOP_014_REV04,
        SAF_SOP_003_REV05,
        MNT_MAN_CNC_02_REV02,
        SAMPLE_QUESTIONS,
    )
}


def get_spec(source_filename: str) -> DocumentSpec | None:
    """Return the verified spec for ``source_filename``, or ``None`` if unknown."""
    return DOCUMENT_SPECS.get(source_filename)


def specs_by_status(status: str) -> list[DocumentSpec]:
    """Return every registered spec with the given document status."""
    return [spec for spec in DOCUMENT_SPECS.values() if spec.document_status == status]
