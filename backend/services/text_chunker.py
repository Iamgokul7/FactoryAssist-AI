"""Splits extracted PDF pages into overlapping, page-scoped text chunks.

Chunks never cross a page boundary and never combine two documents or two
revisions, so every chunk can be traced back to exactly one page of one
document revision.
"""

from __future__ import annotations

from backend.services.document_models import ExtractedPage, TextChunk

# Defaults sit inside the 700-1000 character chunk target with 100-150
# characters of overlap. Both are overridable through settings.
DEFAULT_CHUNK_SIZE = 900
DEFAULT_CHUNK_OVERLAP = 150

# Do not cut a chunk before it has reached this fraction of the target size,
# so chunks stay near the target length instead of ending at the first indent.
_MIN_FILL_RATIO = 0.75

# A short page-end fragment is folded into the previous chunk while the result
# stays within this multiple of the target size.
_MAX_MERGE_RATIO = 1.15

# Smallest overlap worth detecting when merging a fragment.
_MIN_OVERLAP_PROBE = 20


def chunk_document(
    pages: list[ExtractedPage],
    *,
    document_code: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[TextChunk]:
    """Turn a document's pages into chunks, preserving page identity."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be >= 0 and smaller than chunk_size")

    chunks: list[TextChunk] = []
    for page in pages:
        pieces = split_page_text(
            page.page_text, chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )
        for index, piece in enumerate(pieces, start=1):
            chunks.append(
                TextChunk(
                    chunk_id=f"{page.document_id}-p{page.page_number:03d}-c{index:03d}",
                    document_id=page.document_id,
                    document_title=page.document_title,
                    document_code=document_code,
                    revision=page.revision,
                    document_status=page.document_status,
                    source_filename=page.source_filename,
                    page_number=page.page_number,
                    # Chunks never span pages, so the range is the single page.
                    page_range=str(page.page_number),
                    chunk_index=index,
                    char_count=len(piece),
                    chunk_text=piece,
                )
            )
    return chunks


def split_page_text(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Split one page's text into overlapping chunks on natural boundaries."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    minimum_fill = int(chunk_size * _MIN_FILL_RATIO)
    chunks: list[str] = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + chunk_size, length)
        if end < length:
            end = _snap_back(text, start, end, minimum_fill)

        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)

        if end >= length:
            break

        next_start = _snap_forward(text, max(end - chunk_overlap, start + 1), end)
        # Guarantee forward progress even when the overlap lands on a long word.
        start = next_start if next_start > start else end

    return _merge_short_tail(chunks, chunk_size, minimum_fill)


def _merge_short_tail(
    pieces: list[str], chunk_size: int, minimum_fill: int
) -> list[str]:
    """Fold a small trailing fragment into the previous chunk when it fits.

    Without this, a page often ends with a very short chunk that is a poor
    retrieval unit. Merging also drops the duplicated overlap between the two.
    """
    if len(pieces) < 2 or len(pieces[-1]) >= minimum_fill:
        return pieces

    previous, tail = pieces[-2], pieces[-1]
    merged = previous + tail[_shared_overlap(previous, tail) :]
    if len(merged) > chunk_size * _MAX_MERGE_RATIO:
        return pieces
    return [*pieces[:-2], merged]


def _shared_overlap(previous: str, tail: str) -> int:
    """Length of the longest suffix of ``previous`` that prefixes ``tail``."""
    for length in range(min(len(previous), len(tail)), _MIN_OVERLAP_PROBE - 1, -1):
        if previous[-length:] == tail[:length]:
            return length
    return 0


def _snap_back(text: str, start: int, end: int, minimum_fill: int) -> int:
    """Pull ``end`` back to a paragraph, line or word break so words stay whole."""
    limit = min(start + minimum_fill, end - 1)
    for separator in ("\n\n", "\n", " "):
        position = text.rfind(separator, limit, end)
        if position > start:
            return position

    # No break after ``limit``: accept the last space before ``end``.
    position = text.rfind(" ", start + 1, end)
    if position > start:
        return position
    return end


def _snap_forward(text: str, position: int, limit: int) -> int:
    """Move ``position`` forward to the start of the next word."""
    position = min(position, limit)
    while position < limit and not text[position].isspace():
        position += 1
    while position < limit and text[position].isspace():
        position += 1
    return position
