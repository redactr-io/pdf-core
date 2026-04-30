from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import fitz

from pdf_service.core.branding import generate_redaction_id
from pdf_service.core.verification import _check_residual_content

if TYPE_CHECKING:
    from pdf_service.core.types import (
        DetectRiskyAnnotationsResult,
        RiskyAnnotationFinding,
    )

logger = logging.getLogger(__name__)


# PyMuPDF annotation type → string subtype label exposed in the API.
_RISKY_SUBTYPES_BY_TYPE: dict[int, str] = {
    fitz.PDF_ANNOT_SQUARE: "Square",
    fitz.PDF_ANNOT_CIRCLE: "Circle",
    fitz.PDF_ANNOT_POLYGON: "Polygon",
    fitz.PDF_ANNOT_INK: "Ink",
}

# Near-white fills (>= 245/255 on every channel) are treated as transparent
# against the page background — matches the pdf-lib viewer's guard.
_NEAR_WHITE_THRESHOLD = 245 / 255


def _is_visibly_filled(annot: fitz.Annot) -> bool:
    """True if the annotation has a non-transparent /IC fill colour."""
    fill = annot.colors.get("fill")
    if not fill or len(fill) < 3:
        return False
    r, g, b = fill[:3]
    return not (
        r >= _NEAR_WHITE_THRESHOLD
        and g >= _NEAR_WHITE_THRESHOLD
        and b >= _NEAR_WHITE_THRESHOLD
    )


def _is_risky(annot: fitz.Annot, subtype: str) -> bool:
    """`Ink` is always risky; shape annotations require a visible fill."""
    if subtype == "Ink":
        return True
    return _is_visibly_filled(annot)


def detect_risky_annotations(pdf_data: bytes) -> DetectRiskyAnnotationsResult:
    """Find annotations that look like redactions but leave content recoverable.

    Walks every page's annotations, filters to filled Square/Circle/Polygon
    or any Ink, then keeps only those that have residual text or images
    underneath their /Rect.
    """
    if not pdf_data:
        raise ValueError("Empty PDF data")

    try:
        doc = fitz.open(stream=pdf_data, filetype="pdf")
    except Exception as exc:
        raise ValueError("Invalid or corrupt PDF") from exc

    findings: list[RiskyAnnotationFinding] = []

    with doc:
        page_count = doc.page_count
        for page_num, page in enumerate(doc):
            for annot in page.annots() or []:
                annot_type = annot.type[0]
                subtype = _RISKY_SUBTYPES_BY_TYPE.get(annot_type)
                if subtype is None:
                    continue
                if not _is_risky(annot, subtype):
                    continue

                rect = annot.rect
                if rect.is_empty:
                    continue

                residual_text, has_residual_images = _check_residual_content(
                    page, rect, branding_rects=[]
                )
                if not residual_text and not has_residual_images:
                    continue

                findings.append(
                    {
                        "annotation_id": generate_redaction_id(
                            page_num, rect.x0, rect.y0, rect.x1, rect.y1
                        ),
                        "page": page_num,
                        "x0": rect.x0,
                        "y0": rect.y0,
                        "x1": rect.x1,
                        "y1": rect.y1,
                        "source_subtype": subtype,
                        "has_residual_text": bool(residual_text),
                        "has_residual_images": has_residual_images,
                    }
                )

    logger.info(
        "Detected %d risky annotations across %d pages",
        len(findings),
        page_count,
    )
    return {"findings": findings, "total_findings": len(findings)}
