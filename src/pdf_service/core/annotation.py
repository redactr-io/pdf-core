import logging
import xml.etree.ElementTree as ET

import fitz

from pdf_service.core.branding import generate_redaction_id
from pdf_service.core.types import (
    AnnotationResult,
    SuggestionAnnotationsResult,
    SuggestionInputItem,
)

logger = logging.getLogger(__name__)

XFDF_NS = "http://ns.adobe.com/xfdf/"


def get_suggestion_annotations(
    pdf_data: bytes, suggestions: list[SuggestionInputItem]
) -> SuggestionAnnotationsResult:
    """Localise each suggestion's text on the PDF and produce per-rect annotations.

    Each annotation carries the matched rect coords plus the input's
    metadata (reason / confidence / explanation / recommendation) echoed
    verbatim. pdf-core does not interpret the metadata.

    Per-input `page_number` (when set) filters the search to that
    0-indexed page; omitted searches all pages.
    """
    if not pdf_data:
        raise ValueError("Empty PDF data")

    try:
        doc = fitz.open(stream=pdf_data, filetype="pdf")
    except Exception as exc:
        raise ValueError("Invalid or corrupt PDF") from exc

    with doc:
        annotations: list[AnnotationResult] = []

        root = ET.Element("xfdf", xmlns=XFDF_NS)
        annots_el = ET.SubElement(root, "annots")

        for suggestion in suggestions:
            text = suggestion["text"]
            requested_page = suggestion.get("page_number")
            reason = suggestion.get("reason", "")
            confidence = suggestion.get("confidence", 0.0)
            explanation = suggestion.get("explanation", "")
            recommendation = suggestion.get("recommendation", "")
            pages_to_search: list[int] | range = (
                [requested_page] if requested_page is not None else range(len(doc))
            )

            for page_num in pages_to_search:
                if page_num < 0 or page_num >= len(doc):
                    # Out-of-range page filter: skip silently.
                    continue
                page = doc[page_num]
                matches = page.search_for(text)

                for rect in matches:
                    annotation_id = generate_redaction_id(
                        page_num,
                        rect.x0,
                        rect.y0,
                        rect.x1,
                        rect.y1,
                    )

                    highlight = ET.SubElement(annots_el, "highlight")
                    highlight.set("name", annotation_id)
                    highlight.set("page", str(page_num))
                    highlight.set(
                        "rect",
                        f"{rect.x0:.2f},{rect.y0:.2f},{rect.x1:.2f},{rect.y1:.2f}",
                    )
                    contents = ET.SubElement(highlight, "contents")
                    contents.text = text

                    annotations.append(
                        {
                            "annotation_id": annotation_id,
                            "page": page_num,
                            "text": text,
                            "x0": rect.x0,
                            "y0": rect.y0,
                            "x1": rect.x1,
                            "y1": rect.y1,
                            "reason": reason,
                            "confidence": confidence,
                            "explanation": explanation,
                            "recommendation": recommendation,
                        }
                    )

        xfdf_str = ET.tostring(root, encoding="unicode", xml_declaration=True)

        logger.info(
            "Generated %d annotations for %d suggestion inputs in a %d-page document",
            len(annotations),
            len(suggestions),
            len(doc),
        )

        return {
            "xfdf": xfdf_str,
            "total_annotations": len(annotations),
            "annotations": annotations,
        }
