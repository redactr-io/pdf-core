import logging
import uuid
import xml.etree.ElementTree as ET

import fitz

from pdf_service.core.types import SuggestionAnnotationsResult

logger = logging.getLogger(__name__)

XFDF_NS = "http://ns.adobe.com/xfdf/"


def get_suggestion_annotations(pdf_data: bytes, texts: list[str]) -> SuggestionAnnotationsResult:
    if not pdf_data:
        raise ValueError("Empty PDF data")

    try:
        doc = fitz.open(stream=pdf_data, filetype="pdf")
    except Exception:
        raise ValueError("Invalid or corrupt PDF")

    with doc:
        total_suggestions = 0
        results = []

        root = ET.Element("xfdf", xmlns=XFDF_NS)
        annots_el = ET.SubElement(root, "annots")

        for text in texts:
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_height = page.rect.height
                matches = page.search_for(text)
                occurrences = len(matches)

                for rect in matches:
                    annot_name = str(uuid.uuid4())
                    xfdf_y0 = page_height - rect.y1
                    xfdf_y1 = page_height - rect.y0

                    highlight = ET.SubElement(annots_el, "highlight")
                    highlight.set("name", annot_name)
                    highlight.set("page", str(page_num))
                    highlight.set(
                        "rect",
                        f"{rect.x0:.2f},{xfdf_y0:.2f},{rect.x1:.2f},{xfdf_y1:.2f}",
                    )
                    contents = ET.SubElement(highlight, "contents")
                    contents.text = text
                    total_suggestions += 1

                if occurrences > 0:
                    results.append({
                        "text": text,
                        "page": page_num,
                        "occurrences_found": occurrences,
                    })

        xfdf_str = ET.tostring(root, encoding="unicode", xml_declaration=True)

        logger.info(
            "Generated %d suggestions for %d text queries across %d pages",
            total_suggestions, len(texts), len(doc),
        )

        return {
            "xfdf": xfdf_str,
            "total_suggestions": total_suggestions,
            "results": results,
        }
