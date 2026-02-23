from __future__ import annotations

import hashlib
import logging
import xml.etree.ElementTree as ET
from collections import defaultdict
from importlib.metadata import version
from typing import TYPE_CHECKING

import fitz

from pdf_service.core.branding import (
    BrandingStyle,
    draw_branding,
    generate_redaction_id,
)

if TYPE_CHECKING:
    from pdf_service.core.types import (
        RedactionLogEntryResult,
        RedactionResult,
        RedactionStyleConfig,
    )

logger = logging.getLogger(__name__)

XFDF_NS = "http://ns.adobe.com/xfdf/"


def apply_redactions(
    pdf_data: bytes,
    xfdf: str,
    style_config: RedactionStyleConfig | None = None,
) -> RedactionResult:
    if not pdf_data:
        raise ValueError("Empty PDF data")
    if not xfdf:
        raise ValueError("Empty XFDF data")

    try:
        doc = fitz.open(stream=pdf_data, filetype="pdf")
    except Exception as exc:
        raise ValueError("Invalid or corrupt PDF") from exc

    branding_style = BrandingStyle.from_config(style_config)

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
        # Store (rect, redaction_id) per page
        redaction_rects: dict[int, list[tuple[fitz.Rect, str]]] = defaultdict(list)

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
            rid = generate_redaction_id(page_num, rect.x0, rect.y0, rect.x1, rect.y1)
            redaction_rects[page_num].append((rect, rid))
            redaction_count += 1

        if skipped > 0:
            logger.warning("Skipped %d annotations with invalid page/rect", skipped)

        for page in doc:
            page.apply_redactions()

        # Re-add Redact annotations as structural markers and apply branding
        for page_num, rect_entries in redaction_rects.items():
            page = doc[page_num]
            for rect, rid in rect_entries:
                if branding_style:
                    # Transparent Redact annotation as structural marker;
                    # the visible indicator is a separate annotation on top.
                    annot = page.add_redact_annot(rect, cross_out=False)
                    annot.set_opacity(0)
                    annot.update(cross_out=False)
                    draw_branding(page, rect, rid, branding_style)
                else:
                    page.add_redact_annot(rect, fill=(0, 0, 0), cross_out=True)

        # Build redaction audit log
        redaction_log: list[RedactionLogEntryResult] = []
        for page_num, rect_entries in redaction_rects.items():
            for rect, rid in rect_entries:
                redaction_log.append(
                    {
                        "redaction_id": rid,
                        "page": page_num,
                        "x0": rect.x0,
                        "y0": rect.y0,
                        "x1": rect.x1,
                        "y1": rect.y1,
                    }
                )

        pkg_version = version("pdf-core")
        doc.set_metadata({"producer": f"PDF Core v{pkg_version} by redactr.io"})

        output_bytes = doc.tobytes(garbage=4, deflate=True)
        content_hash = hashlib.sha256(output_bytes).digest()

        logger.info("Applied %d redactions across %d pages", redaction_count, len(doc))

        return {
            "pdf_data": output_bytes,
            "redactions_applied": redaction_count,
            "content_hash": content_hash,
            "redaction_log": redaction_log,
        }
