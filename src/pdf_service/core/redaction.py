import hashlib
import logging
from importlib.metadata import version
import xml.etree.ElementTree as ET

import fitz

from pdf_service.core.types import RedactionResult

logger = logging.getLogger(__name__)

XFDF_NS = "http://ns.adobe.com/xfdf/"


def apply_redactions(pdf_data: bytes, xfdf: str) -> RedactionResult:
    if not pdf_data:
        raise ValueError("Empty PDF data")
    if not xfdf:
        raise ValueError("Empty XFDF data")

    try:
        doc = fitz.open(stream=pdf_data, filetype="pdf")
    except Exception:
        raise ValueError("Invalid or corrupt PDF")

    with doc:
        try:
            root = ET.fromstring(xfdf)
        except ET.ParseError:
            raise ValueError("Malformed XFDF")

        # Find highlight elements with or without namespace
        highlights = root.findall(f".//{{{XFDF_NS}}}highlight")
        if not highlights:
            highlights = root.findall(".//highlight")

        redaction_count = 0
        skipped = 0
        for hl in highlights:
            page_num = int(hl.get("page", "0"))
            rect_str = hl.get("rect", "")
            if not rect_str or page_num < 0 or page_num >= len(doc):
                skipped += 1
                continue

            coords = [float(v) for v in rect_str.split(",")]
            if len(coords) != 4:
                skipped += 1
                continue

            x0, xfdf_y0, x1, xfdf_y1 = coords
            page = doc[page_num]
            page_height = page.rect.height

            # Reverse coordinate conversion: XFDF bottom-left → PyMuPDF top-left
            y0 = page_height - xfdf_y1
            y1 = page_height - xfdf_y0

            page.add_redact_annot(fitz.Rect(x0, y0, x1, y1), fill=(0, 0, 0))
            redaction_count += 1

        if skipped > 0:
            logger.warning("Skipped %d highlights with invalid page/rect", skipped)

        for page in doc:
            page.apply_redactions()

        pkg_version = version("pdf-core")
        doc.set_metadata({"producer": f"PDF Core v{pkg_version} by redactr.io"})

        output_bytes = doc.tobytes(garbage=4, deflate=True)
        content_hash = hashlib.sha256(output_bytes).digest()

        logger.info("Applied %d redactions across %d pages", redaction_count, len(doc))

        return {
            "pdf_data": output_bytes,
            "redactions_applied": redaction_count,
            "content_hash": content_hash,
        }
