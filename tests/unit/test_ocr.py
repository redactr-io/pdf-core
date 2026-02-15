import fitz
import pytest

from pdf_service.core.ocr import ocr_page


class TestOcrPage:
    def test_ocr_extracts_text_from_scanned_page(self, scanned_pdf):
        """OCR on a red block image — may not extract meaningful text,
        but should not error if Tesseract is installed."""
        doc = fitz.open(stream=scanned_pdf, filetype="pdf")
        page = doc[0]
        try:
            text = ocr_page(page)
            # Just verify it returns a string without erroring
            assert isinstance(text, str)
        except RuntimeError as e:
            if "Tesseract" in str(e):
                pytest.skip("Tesseract not installed")
            raise
        finally:
            doc.close()

    def test_ocr_returns_string(self, text_pdf):
        """OCR on a text page should return text."""
        doc = fitz.open(stream=text_pdf, filetype="pdf")
        page = doc[0]
        try:
            text = ocr_page(page)
            assert isinstance(text, str)
            assert len(text) > 0
        except RuntimeError as e:
            if "Tesseract" in str(e):
                pytest.skip("Tesseract not installed")
            raise
        finally:
            doc.close()
