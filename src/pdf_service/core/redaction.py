import hashlib
import logging
import xml.etree.ElementTree as ET
from collections import defaultdict
from importlib.metadata import version

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
    except Exception as exc:
        raise ValueError("Invalid or corrupt PDF") from exc

    with doc:
        try:
            root = ET.fromstring(xfdf)
        except ET.ParseError as exc:
            raise ValueError("Malformed XFDF") from exc

        # Accept highlight, redact, and square annotation types
        annot_types = ("highlight", "redact", "square")
        annotations: list[ET.Element] = []
        for tag in annot_types:
            annotations.extend(root.findall(f".//{{{XFDF_NS}}}{tag}"))
        if not annotations:
            for tag in annot_types:
                annotations.extend(root.findall(f".//{tag}"))

        redaction_count = 0
        skipped = 0
        redaction_rects: dict[int, list[fitz.Rect]] = defaultdict(list)

        for hl in annotations:
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

            rect = fitz.Rect(x0, y0, x1, y1)
            page.add_redact_annot(rect, fill=(0, 0, 0))
            redaction_rects[page_num].append(rect)
            redaction_count += 1

        if skipped > 0:
            logger.warning("Skipped %d annotations with invalid page/rect", skipped)

        for page in doc:
            page.apply_redactions()

        # Re-add Redact annotations as structural markers so verification
        # tools can identify which areas were intentionally redacted.
        for page_num, rects in redaction_rects.items():
            page = doc[page_num]
            for rect in rects:
                page.add_redact_annot(rect, fill=(0, 0, 0))

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
