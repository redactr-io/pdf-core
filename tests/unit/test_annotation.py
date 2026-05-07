import xml.etree.ElementTree as ET

import pytest

from pdf_service.core.annotation import XFDF_NS, get_suggestion_annotations


def _input(text: str, page_number: int | None = None, **metadata) -> dict:
    """Build a SuggestionInputItem with sensible metadata defaults."""
    inp: dict = {
        "text": text,
        "reason": metadata.get("reason", "name"),
        "confidence": metadata.get("confidence", 0.9),
        "explanation": metadata.get("explanation", "test"),
        "recommendation": metadata.get("recommendation", "redact"),
    }
    if page_number is not None:
        inp["page_number"] = page_number
    return inp


class TestGetSuggestionAnnotations:
    def test_returns_valid_xfdf_xml(self, text_pdf):
        result = get_suggestion_annotations(text_pdf, [_input("John Smith")])
        root = ET.fromstring(result["xfdf"])
        assert root.tag == f"{{{XFDF_NS}}}xfdf" or root.tag == "xfdf"

    def test_highlight_elements_present(self, text_pdf):
        result = get_suggestion_annotations(text_pdf, [_input("John Smith")])
        root = ET.fromstring(result["xfdf"])
        highlights = root.findall(f".//{{{XFDF_NS}}}highlight")
        if not highlights:
            highlights = root.findall(".//highlight")
        assert len(highlights) >= 1

    def test_highlight_has_hash_name(self, text_pdf):
        result = get_suggestion_annotations(text_pdf, [_input("John Smith")])
        root = ET.fromstring(result["xfdf"])
        highlights = root.findall(f".//{{{XFDF_NS}}}highlight")
        if not highlights:
            highlights = root.findall(".//highlight")
        for hl in highlights:
            name = hl.get("name")
            assert len(name) == 12
            int(name, 16)

    def test_highlight_has_page_and_rect(self, text_pdf):
        result = get_suggestion_annotations(text_pdf, [_input("John Smith")])
        root = ET.fromstring(result["xfdf"])
        highlights = root.findall(f".//{{{XFDF_NS}}}highlight")
        if not highlights:
            highlights = root.findall(".//highlight")
        for hl in highlights:
            assert hl.get("page") is not None
            rect = hl.get("rect")
            coords = rect.split(",")
            assert len(coords) == 4
            for c in coords:
                float(c)

    def test_coordinate_sanity(self, text_pdf):
        result = get_suggestion_annotations(text_pdf, [_input("John Smith")])
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
        result = get_suggestion_annotations(text_pdf, [_input("John Smith")])
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

    def test_multiple_inputs(self, text_pdf):
        result = get_suggestion_annotations(
            text_pdf,
            [_input("John Smith"), _input("123-45-6789")],
        )
        assert result["total_annotations"] >= 2

    def test_no_match_returns_zero_suggestions(self, text_pdf):
        result = get_suggestion_annotations(text_pdf, [_input("nonexistent text xyz")])
        assert result["total_annotations"] == 0
        assert result["annotations"] == []

    def test_annotations_carry_coords_and_metadata(self, text_pdf):
        """Each annotation carries page + rect coords + echoed metadata."""
        result = get_suggestion_annotations(
            text_pdf,
            [
                _input(
                    "John Smith",
                    reason="name",
                    confidence=0.95,
                    explanation="patient name",
                    recommendation="redact",
                )
            ],
        )
        assert len(result["annotations"]) >= 1
        ann = result["annotations"][0]
        assert ann["text"] == "John Smith"
        assert ann["page"] == 0
        assert ann["x0"] < ann["x1"]
        assert ann["y0"] < ann["y1"]
        assert len(ann["annotation_id"]) == 12
        int(ann["annotation_id"], 16)
        # Metadata echoed verbatim:
        assert ann["reason"] == "name"
        assert ann["confidence"] == pytest.approx(0.95)
        assert ann["explanation"] == "patient name"
        assert ann["recommendation"] == "redact"

    def test_annotation_id_matches_xfdf_name(self, text_pdf):
        """The annotation_id on each Annotation matches the XFDF highlight's name."""
        result = get_suggestion_annotations(text_pdf, [_input("John Smith")])
        root = ET.fromstring(result["xfdf"])
        highlights = root.findall(f".//{{{XFDF_NS}}}highlight")
        if not highlights:
            highlights = root.findall(".//highlight")
        xfdf_names = {hl.get("name") for hl in highlights}
        annotation_ids = {a["annotation_id"] for a in result["annotations"]}
        assert xfdf_names == annotation_ids

    def test_page_number_filter_restricts_search(self, multi_page_pdf):
        """page_number on input filters the search to that 0-indexed page only."""
        # "Project Alpha" is on page 2 (0-indexed page 1) per conftest.
        result_page_0 = get_suggestion_annotations(
            multi_page_pdf,
            [_input("Project Alpha", page_number=0)],
        )
        assert result_page_0["total_annotations"] == 0
        result_page_1 = get_suggestion_annotations(
            multi_page_pdf,
            [_input("Project Alpha", page_number=1)],
        )
        assert result_page_1["total_annotations"] >= 1
        assert all(a["page"] == 1 for a in result_page_1["annotations"])

    def test_no_page_filter_searches_all_pages(self, multi_page_pdf):
        """Omitting page_number searches every page (preserves Pro's behaviour)."""
        result = get_suggestion_annotations(multi_page_pdf, [_input("Project Alpha")])
        assert result["total_annotations"] >= 1
        assert any(a["page"] == 1 for a in result["annotations"])

    def test_explicit_none_page_filter_searches_all_pages(self, multi_page_pdf):
        """Explicit page_number=None is equivalent to omitting the field."""
        result = get_suggestion_annotations(
            multi_page_pdf,
            [{"text": "Project Alpha", "page_number": None}],
        )
        assert result["total_annotations"] >= 1
        assert any(a["page"] == 1 for a in result["annotations"])

    def test_same_text_two_pages_two_separate_inputs_disambiguates(self):
        """Two SuggestionInputs for the same text on different pages produce
        two separate Annotations, each with its own metadata."""
        import fitz

        doc = fitz.open()
        for _i in range(2):
            page = doc.new_page()
            page.insert_text((72, 72), "James Okafor appears here.", fontsize=12)
        pdf_data = doc.tobytes()
        doc.close()

        result = get_suggestion_annotations(
            pdf_data,
            [
                _input(
                    "James Okafor", page_number=0, reason="name", explanation="page 0"
                ),
                _input(
                    "James Okafor", page_number=1, reason="name", explanation="page 1"
                ),
            ],
        )

        assert result["total_annotations"] == 2
        annotations_by_page = {a["page"]: a for a in result["annotations"]}
        assert annotations_by_page[0]["explanation"] == "page 0"
        assert annotations_by_page[1]["explanation"] == "page 1"

    def test_metadata_fields_default_to_empty_when_absent(self, text_pdf):
        """An input with only `text` produces annotations with empty metadata."""
        result = get_suggestion_annotations(text_pdf, [{"text": "John Smith"}])
        assert len(result["annotations"]) >= 1
        ann = result["annotations"][0]
        assert ann["reason"] == ""
        assert ann["confidence"] == 0.0
        assert ann["explanation"] == ""
        assert ann["recommendation"] == ""

    def test_empty_suggestions_list_returns_empty_response(self, text_pdf):
        result = get_suggestion_annotations(text_pdf, [])
        assert result["total_annotations"] == 0
        assert result["annotations"] == []
        # XFDF still valid (empty annots root).
        root = ET.fromstring(result["xfdf"])
        assert root.tag == f"{{{XFDF_NS}}}xfdf" or root.tag == "xfdf"

    def test_raises_for_empty_bytes(self):
        with pytest.raises(ValueError, match="Empty PDF data"):
            get_suggestion_annotations(b"", [_input("test")])

    def test_raises_for_corrupt_pdf(self):
        with pytest.raises(ValueError, match="Invalid or corrupt PDF"):
            get_suggestion_annotations(b"not a pdf", [_input("test")])
