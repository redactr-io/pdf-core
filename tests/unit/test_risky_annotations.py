from pdf_service.core.risky_annotations import detect_risky_annotations


class TestDetectRiskyAnnotations:
    def test_filled_square_over_text_is_flagged(self, pdf_with_filled_square_over_text):
        result = detect_risky_annotations(pdf_with_filled_square_over_text)

        assert result["total_findings"] == 1
        finding = result["findings"][0]
        assert finding["source_subtype"] == "Square"
        assert finding["page"] == 0
        assert finding["has_residual_text"] is True
        assert finding["has_residual_images"] is False
        # Deterministic 12-char hex name from generate_redaction_id
        assert len(finding["annotation_id"]) == 12
        assert all(c in "0123456789abcdef" for c in finding["annotation_id"])

    def test_unfilled_square_is_not_flagged(self, pdf_with_unfilled_square_over_text):
        result = detect_risky_annotations(pdf_with_unfilled_square_over_text)
        assert result["total_findings"] == 0

    def test_filled_square_over_whitespace_is_not_flagged(
        self, pdf_with_filled_square_over_whitespace
    ):
        result = detect_risky_annotations(pdf_with_filled_square_over_whitespace)
        assert result["total_findings"] == 0

    def test_ink_over_text_is_flagged(self, pdf_with_ink_over_text):
        result = detect_risky_annotations(pdf_with_ink_over_text)
        assert result["total_findings"] == 1
        assert result["findings"][0]["source_subtype"] == "Ink"
        assert result["findings"][0]["has_residual_text"] is True

    def test_highlight_is_not_flagged(self, pdf_with_highlight_over_text):
        # Highlights are intentionally out of scope (clearly markup, not
        # a fake redaction).
        result = detect_risky_annotations(pdf_with_highlight_over_text)
        assert result["total_findings"] == 0

    def test_filled_circle_over_text_is_flagged(self, pdf_with_filled_circle_over_text):
        result = detect_risky_annotations(pdf_with_filled_circle_over_text)
        assert result["total_findings"] == 1
        assert result["findings"][0]["source_subtype"] == "Circle"

    def test_filled_polygon_over_text_is_flagged(
        self, pdf_with_filled_polygon_over_text
    ):
        result = detect_risky_annotations(pdf_with_filled_polygon_over_text)
        assert result["total_findings"] == 1
        assert result["findings"][0]["source_subtype"] == "Polygon"

    def test_pdf_with_no_annotations_returns_empty_findings(self, text_pdf):
        result = detect_risky_annotations(text_pdf)
        assert result == {"findings": [], "total_findings": 0}

    def test_empty_pdf_data_raises_value_error(self):
        import pytest as _pytest

        with _pytest.raises(ValueError, match="Empty PDF data"):
            detect_risky_annotations(b"")

    def test_corrupt_pdf_raises_value_error(self):
        import pytest as _pytest

        with _pytest.raises(ValueError, match="Invalid or corrupt PDF"):
            detect_risky_annotations(b"%PDF-not-actually-a-pdf")

    def test_finding_name_is_deterministic(self, pdf_with_filled_square_over_text):
        first = detect_risky_annotations(pdf_with_filled_square_over_text)
        second = detect_risky_annotations(pdf_with_filled_square_over_text)
        first_id = first["findings"][0]["annotation_id"]
        second_id = second["findings"][0]["annotation_id"]
        assert first_id == second_id

    def test_ink_over_whitespace_is_not_flagged(self, pdf_with_ink_over_whitespace):
        # Ink is always a candidate, but with no text/image underneath the
        # residual-content gate must still suppress the finding.
        result = detect_risky_annotations(pdf_with_ink_over_whitespace)
        assert result["total_findings"] == 0

    def test_filled_square_over_image_is_flagged(
        self, pdf_with_filled_square_over_image
    ):
        # Exercises the has_residual_images branch — a black Square covering
        # a small embedded image with no text underneath should still flag.
        result = detect_risky_annotations(pdf_with_filled_square_over_image)
        assert result["total_findings"] == 1
        finding = result["findings"][0]
        assert finding["source_subtype"] == "Square"
        assert finding["has_residual_images"] is True
