import pytest

from pdf_service.core.text_extraction import extract_text


class TestExtractText:
    def test_extracts_text_from_single_page(self, text_pdf):
        pages = list(extract_text(text_pdf, None, False, None))
        assert len(pages) == 1
        assert "John Smith" in pages[0]["text"]
        assert "123-45-6789" in pages[0]["text"]

    def test_extracts_from_specific_pages(self, multi_page_pdf):
        pages = list(extract_text(multi_page_pdf, [1], False, None))
        assert len(pages) == 1
        assert pages[0]["page_number"] == 1
        assert "Project Alpha" in pages[0]["text"]

    def test_returns_all_pages_when_no_filter(self, multi_page_pdf):
        pages = list(extract_text(multi_page_pdf, None, False, None))
        assert len(pages) == 3

    def test_returns_blocks_with_positions(self, text_pdf):
        pages = list(extract_text(text_pdf, None, True, None))
        assert len(pages) == 1
        blocks = pages[0]["blocks"]
        assert len(blocks) > 0
        block = blocks[0]
        assert "text" in block
        assert "x0" in block
        assert "y0" in block
        assert "x1" in block
        assert "y1" in block

    def test_empty_text_for_scanned_pages(self, scanned_pdf):
        pages = list(extract_text(scanned_pdf, None, False, None))
        assert len(pages) == 1
        assert pages[0]["text"].strip() == ""

    def test_handles_multi_page(self, multi_page_pdf):
        pages = list(extract_text(multi_page_pdf, None, False, None))
        assert len(pages) == 3
        assert "John Smith" in pages[0]["text"]
        assert "Project Alpha" in pages[1]["text"]
        assert "$50,000" in pages[2]["text"]

    def test_raises_for_empty_bytes(self):
        with pytest.raises(ValueError, match="Empty PDF data"):
            list(extract_text(b"", None, False, None))

    def test_raises_for_corrupt_data(self):
        with pytest.raises(ValueError, match="Invalid or corrupt PDF"):
            list(extract_text(b"not a pdf", None, False, None))

    def test_raises_for_invalid_page_numbers(self, text_pdf):
        with pytest.raises(ValueError, match="Page numbers out of range"):
            list(extract_text(text_pdf, [99], False, None))

    def test_no_blocks_when_positions_disabled(self, text_pdf):
        pages = list(extract_text(text_pdf, None, False, None))
        assert pages[0]["blocks"] == []
