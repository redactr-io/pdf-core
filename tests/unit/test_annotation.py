import uuid
import xml.etree.ElementTree as ET

import pytest

from pdf_service.core.annotation import XFDF_NS, get_suggestion_annotations


class TestGetSuggestionAnnotations:
    def test_returns_valid_xfdf_xml(self, text_pdf):
        result = get_suggestion_annotations(text_pdf, ["John Smith"])
        root = ET.fromstring(result["xfdf"])
        assert root.tag == f"{{{XFDF_NS}}}xfdf" or root.tag == "xfdf"

    def test_highlight_elements_present(self, text_pdf):
        result = get_suggestion_annotations(text_pdf, ["John Smith"])
        root = ET.fromstring(result["xfdf"])
        highlights = root.findall(f".//{{{XFDF_NS}}}highlight")
        if not highlights:
            highlights = root.findall(".//highlight")
        assert len(highlights) >= 1

    def test_highlight_has_uuid_name(self, text_pdf):
        result = get_suggestion_annotations(text_pdf, ["John Smith"])
        root = ET.fromstring(result["xfdf"])
        highlights = root.findall(f".//{{{XFDF_NS}}}highlight")
        if not highlights:
            highlights = root.findall(".//highlight")
        for hl in highlights:
            uuid.UUID(hl.get("name"))  # raises if invalid

    def test_highlight_has_page_and_rect(self, text_pdf):
        result = get_suggestion_annotations(text_pdf, ["John Smith"])
        root = ET.fromstring(result["xfdf"])
        highlights = root.findall(f".//{{{XFDF_NS}}}highlight")
        if not highlights:
            highlights = root.findall(".//highlight")
        for hl in highlights:
            assert hl.get("page") is not None
            rect = hl.get("rect")
            assert rect is not None
            coords = rect.split(",")
            assert len(coords) == 4
            for c in coords:
                float(c)  # raises if not a number

    def test_coordinate_sanity(self, text_pdf):
        """XFDF y-coords should use bottom-left origin (y0 < y1)."""
        result = get_suggestion_annotations(text_pdf, ["John Smith"])
        root = ET.fromstring(result["xfdf"])
        highlights = root.findall(f".//{{{XFDF_NS}}}highlight")
        if not highlights:
            highlights = root.findall(".//highlight")
        for hl in highlights:
            coords = [float(v) for v in hl.get("rect").split(",")]
            x0, y0, x1, y1 = coords
            assert x0 < x1
            assert y0 < y1

    def test_contents_text(self, text_pdf):
        result = get_suggestion_annotations(text_pdf, ["John Smith"])
        root = ET.fromstring(result["xfdf"])
        highlights = root.findall(f".//{{{XFDF_NS}}}highlight")
        if not highlights:
            highlights = root.findall(".//highlight")
        for hl in highlights:
            contents = hl.find(f"{{{XFDF_NS}}}contents")
            if contents is None:
                contents = hl.find("contents")
            assert contents is not None
            assert contents.text == "John Smith"

    def test_multiple_texts(self, text_pdf):
        result = get_suggestion_annotations(text_pdf, ["John Smith", "123-45-6789"])
        assert result["total_suggestions"] >= 2

    def test_no_match_returns_zero_suggestions(self, text_pdf):
        result = get_suggestion_annotations(text_pdf, ["nonexistent text xyz"])
        assert result["total_suggestions"] == 0

    def test_results_contain_per_page_info(self, multi_page_pdf):
        result = get_suggestion_annotations(multi_page_pdf, ["Project Alpha"])
        found = [r for r in result["results"] if r["occurrences_found"] > 0]
        assert len(found) >= 1
        assert found[0]["page"] == 1  # Project Alpha is on page 2 (0-indexed)

    def test_raises_for_empty_bytes(self):
        with pytest.raises(ValueError, match="Empty PDF data"):
            get_suggestion_annotations(b"", ["test"])

    def test_raises_for_corrupt_pdf(self):
        with pytest.raises(ValueError, match="Invalid or corrupt PDF"):
            get_suggestion_annotations(b"not a pdf", ["test"])
