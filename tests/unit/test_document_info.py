import pytest

from pdf_service.core.document_info import get_document_info


class TestGetDocumentInfo:
    def test_single_page_count(self, text_pdf):
        result = get_document_info(text_pdf)
        assert result["page_count"] == 1

    def test_multi_page_count(self, multi_page_pdf):
        result = get_document_info(multi_page_pdf)
        assert result["page_count"] == 3

    def test_detects_text_content(self, text_pdf):
        result = get_document_info(text_pdf)
        assert result["has_text_content"] is True

    def test_detects_no_text_on_scanned(self, scanned_pdf):
        result = get_document_info(scanned_pdf)
        assert result["pages"][0]["has_text"] is False
        assert result["pages"][0]["has_images"] is True

    def test_detects_likely_scanned(self, scanned_pdf):
        result = get_document_info(scanned_pdf)
        assert result["pages"][0]["likely_scanned"] is True

    def test_reports_annotation_count(self):
        import fitz

        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Hello World", fontsize=12)
        for rect in page.search_for("Hello"):
            page.add_highlight_annot(rect)
        pdf_data = doc.tobytes()
        doc.close()

        result = get_document_info(pdf_data)
        assert result["has_annotations"] is True
        assert result["existing_annotation_count"] >= 1

    def test_page_dimensions(self, text_pdf):
        result = get_document_info(text_pdf)
        page = result["pages"][0]
        assert page["width"] > 0
        assert page["height"] > 0

    def test_returns_metadata(self, text_pdf):
        result = get_document_info(text_pdf)
        assert "metadata" in result
        meta = result["metadata"]
        assert "title" in meta
        assert "author" in meta
        assert "producer" in meta
        assert "creator" in meta

    def test_file_size_bytes(self, text_pdf):
        result = get_document_info(text_pdf)
        assert result["file_size_bytes"] == len(text_pdf)

    def test_raises_for_empty_bytes(self):
        with pytest.raises(ValueError, match="Empty PDF data"):
            get_document_info(b"")

    def test_raises_for_corrupt_data(self):
        with pytest.raises(ValueError, match="Invalid or corrupt PDF"):
            get_document_info(b"not a pdf at all")

    def test_raises_for_encrypted_pdf(self, encrypted_pdf):
        with pytest.raises(ValueError, match="PDF is encrypted"):
            get_document_info(encrypted_pdf)

    def test_empty_pdf_has_no_text(self, empty_pdf):
        result = get_document_info(empty_pdf)
        assert result["has_text_content"] is False
        assert result["page_count"] == 1

    def test_mixed_pdf_pages(self, mixed_pdf):
        result = get_document_info(mixed_pdf)
        assert result["page_count"] == 2
        assert result["pages"][0]["has_text"] is True
        assert result["pages"][1]["has_text"] is False
        assert result["pages"][1]["has_images"] is True
