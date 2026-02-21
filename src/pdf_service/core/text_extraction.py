import logging
from collections.abc import Generator
from typing import Any

import fitz

from pdf_service.core.ocr import ocr_page
from pdf_service.core.types import PageTextResult, TextBlockResult

logger = logging.getLogger(__name__)


def extract_text(
    pdf_data: bytes,
    pages: list[int] | None,
    include_positions: bool,
    ocr_options: dict[str, Any] | None,
) -> Generator[PageTextResult]:
    if not pdf_data:
        raise ValueError("Empty PDF data")

    try:
        doc = fitz.open(stream=pdf_data, filetype="pdf")
    except Exception as exc:
        raise ValueError("Invalid or corrupt PDF") from exc

    with doc:
        page_numbers = pages if pages else list(range(len(doc)))

        if pages:
            invalid = [p for p in page_numbers if p < 0 or p >= len(doc)]
            if invalid:
                raise ValueError(
                    f"Page numbers out of range: {invalid} "
                    f"(document has {len(doc)} pages)"
                )

        for page_num in page_numbers:
            page = doc[page_num]
            page_text = page.get_text()
            blocks: list[TextBlockResult] = []

            use_ocr = (
                ocr_options
                and ocr_options.get("enabled")
                and (not page_text.strip() or ocr_options.get("force"))
            )

            if use_ocr and ocr_options:
                language = ocr_options.get("language", "eng")
                logger.info("Running OCR on page %d (language=%s)", page_num, language)
                page_text = ocr_page(page, language=language)

            if include_positions:
                text_dict = page.get_text("dict")
                block_num = 0
                for block in text_dict.get("blocks", []):
                    if block.get("type") != 0:  # skip image blocks
                        continue
                    for line_num, line in enumerate(block.get("lines", [])):
                        line_text = ""
                        for span in line.get("spans", []):
                            line_text += span.get("text", "")
                        bbox = line.get("bbox", (0, 0, 0, 0))
                        blocks.append(
                            {
                                "text": line_text,
                                "x0": bbox[0],
                                "y0": bbox[1],
                                "x1": bbox[2],
                                "y1": bbox[3],
                                "block_number": block_num,
                                "line_number": line_num,
                            }
                        )
                    block_num += 1

            yield {
                "page_number": page_num,
                "text": page_text,
                "blocks": blocks,
            }
