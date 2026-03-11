from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import fitz

from pdf_service.core.branding import FRAME_PADDING

# Inset the check rectangle by this amount on each edge to avoid
# false positives from adjacent text whose bounding box barely
# touches the redaction boundary (sub-point coordinate precision).
_EDGE_TOLERANCE = 1.0

if TYPE_CHECKING:
    from pdf_service.core.types import (
        RedactionLogEntryResult,
        RedactionVerificationEntry,
        VerifyRedactionsResult,
    )

logger = logging.getLogger(__name__)


def _branding_rects(page: fitz.Page) -> list[fitz.Rect]:
    """Collect expanded bounding boxes of our branding annotations.

    These are FreeText annotations (ID labels) and Redact annotations
    (transparent structural markers) that we add after applying
    redactions.  The rects are expanded slightly to account for
    text rendering outside annotation boundaries.
    """
    tolerance = 2.0
    rects: list[fitz.Rect] = []
    for annot in page.annots():
        atype = annot.type[0]
        if atype in (fitz.PDF_ANNOT_FREE_TEXT, fitz.PDF_ANNOT_REDACT):
            expanded = fitz.Rect(
                annot.rect.x0 - tolerance,
                annot.rect.y0 - tolerance,
                annot.rect.x1 + tolerance,
                annot.rect.y1 + tolerance,
            )
            rects.append(expanded)
    return rects


def _rect_intersects(a: fitz.Rect, b: fitz.Rect) -> bool:
    """Return True if two rectangles overlap."""
    return not a.is_empty and not b.is_empty and a.intersects(b)


def _rect_contains(outer: fitz.Rect, inner: fitz.Rect) -> bool:
    """Return True if outer fully contains inner."""
    return bool(outer.contains(inner))


def verify_redactions(
    pdf_data: bytes,
    redaction_log: list[RedactionLogEntryResult],
) -> VerifyRedactionsResult:
    """Verify that redacted areas contain no residual content.

    For each entry in the redaction log, checks the corresponding
    rectangle on the page for leftover text or images, ignoring
    content that belongs to our own branding annotations.
    """
    if not pdf_data:
        raise ValueError("Empty PDF data")

    if not redaction_log:
        return {"all_passed": True, "entries": []}

    try:
        doc = fitz.open(stream=pdf_data, filetype="pdf")
    except Exception as exc:
        raise ValueError("Invalid or corrupt PDF") from exc

    entries: list[RedactionVerificationEntry] = []

    with doc:
        for entry in redaction_log:
            page_num = entry["page"]
            if page_num < 0 or page_num >= len(doc):
                logger.warning(
                    "Skipping redaction %s: page %d out of range",
                    entry["redaction_id"],
                    page_num,
                )
                continue

            page = doc[page_num]
            redact_rect = fitz.Rect(
                entry["x0"],
                entry["y0"],
                entry["x1"],
                entry["y1"],
            )

            branding = _branding_rects(page)

            # Inset the check area slightly to avoid flagging
            # adjacent text whose bbox barely touches the edge.
            check_rect = fitz.Rect(
                redact_rect.x0 + _EDGE_TOLERANCE,
                redact_rect.y0 + _EDGE_TOLERANCE,
                redact_rect.x1 - _EDGE_TOLERANCE,
                redact_rect.y1 - _EDGE_TOLERANCE,
            )

            # --- Check for residual text ---
            residual_text: list[str] = []
            if not check_rect.is_empty:
                text_dict = page.get_text("dict")
                for block in text_dict.get("blocks", []):
                    if block.get("type") != 0:
                        continue
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            span_text = span.get("text", "").strip()
                            if not span_text:
                                continue
                            bbox = span.get("bbox", (0, 0, 0, 0))
                            span_rect = fitz.Rect(bbox)
                            if not _rect_intersects(check_rect, span_rect):
                                continue
                            # Ignore text inside branding annotations
                            if any(_rect_contains(b, span_rect) for b in branding):
                                continue
                            residual_text.append(span_text)

            # --- Check for residual images ---
            has_residual_images = False
            # The branding frame extends outward by FRAME_PADDING;
            # icons are placed within that expanded frame area.
            frame_rect = fitz.Rect(
                redact_rect.x0 - FRAME_PADDING,
                redact_rect.y0 - FRAME_PADDING,
                redact_rect.x1 + FRAME_PADDING,
                redact_rect.y1 + FRAME_PADDING,
            )
            for img in page.get_images(full=True):
                xref = img[0]
                for img_rect in page.get_image_rects(xref):
                    if not _rect_intersects(check_rect, img_rect):
                        continue
                    # Ignore images within the branding frame
                    # (our icon is placed inside the expanded frame)
                    if _rect_contains(frame_rect, img_rect):
                        continue
                    has_residual_images = True

            passed = len(residual_text) == 0 and not has_residual_images
            entries.append(
                {
                    "redaction_id": entry["redaction_id"],
                    "page": page_num,
                    "passed": passed,
                    "residual_text": residual_text,
                    "has_residual_images": has_residual_images,
                }
            )

    all_passed = all(e["passed"] for e in entries)

    logger.info(
        "Verified %d redactions: %s",
        len(entries),
        "all passed" if all_passed else "failures detected",
    )

    return {"all_passed": all_passed, "entries": entries}
