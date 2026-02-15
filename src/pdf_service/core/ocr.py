import logging

import fitz

logger = logging.getLogger(__name__)


def ocr_page(page: fitz.Page, language: str = "eng") -> str:
    try:
        tp = page.get_textpage_ocr(language=language)
        return page.get_text(textpage=tp)
    except RuntimeError as e:
        if "tesseract" in str(e).lower() or "not installed" in str(e).lower():
            raise RuntimeError("Tesseract OCR is not installed") from e
        raise
    except Exception as e:
        if "tesseract" in str(e).lower():
            raise RuntimeError("Tesseract OCR is not installed") from e
        raise
