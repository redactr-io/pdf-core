import fitz
import pytest

from pdf_service.core.annotation import get_suggestion_annotations
from pdf_service.core.branding import generate_redaction_id
from pdf_service.core.redaction import apply_redactions
from pdf_service.core.verification import verify_redactions


class TestVerifyRedactions:
    def test_clean_redaction_passes(self, text_pdf):
        """Properly redacted areas should pass verification."""
        annots = get_suggestion_annotations(text_pdf, ["John Smith"])
        result = apply_redactions(text_pdf, annots["xfdf"])

        vr = verify_redactions(result["pdf_data"], result["redaction_log"])
        assert vr["all_passed"] is True
        assert len(vr["entries"]) == result["redactions_applied"]
        for entry in vr["entries"]:
            assert entry["passed"] is True
            assert entry["residual_text"] == []
            assert entry["has_residual_images"] is False

    def test_clean_branded_redaction_passes(self, text_pdf):
        """Branded redactions should not trigger false positives."""
        style = {
            "fill_color": "#005941",
            "text_color": "#FFFFFF",
            "label_prefix": "ID:",
        }
        annots = get_suggestion_annotations(text_pdf, ["John Smith"])
        result = apply_redactions(text_pdf, annots["xfdf"], style_config=style)

        vr = verify_redactions(result["pdf_data"], result["redaction_log"])
        assert vr["all_passed"] is True

    def test_residual_text_detected(self):
        """Text remaining inside a redaction rect should fail."""
        # Create a PDF with text, then fabricate a redaction log
        # that claims the text area was redacted (without actually
        # removing it).
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "SENSITIVE DATA", fontsize=12)
        pdf_data = doc.tobytes()
        doc.close()

        # Fabricate a log entry covering the text area
        fake_log = [
            {
                "redaction_id": generate_redaction_id(0, 70, 60, 250, 80),
                "page": 0,
                "x0": 70.0,
                "y0": 60.0,
                "x1": 250.0,
                "y1": 80.0,
            }
        ]

        vr = verify_redactions(pdf_data, fake_log)
        assert vr["all_passed"] is False
        failed = [e for e in vr["entries"] if not e["passed"]]
        assert len(failed) == 1
        assert len(failed[0]["residual_text"]) > 0

    def test_empty_redaction_log(self, text_pdf):
        """Empty log should return all_passed with no entries."""
        vr = verify_redactions(text_pdf, [])
        assert vr["all_passed"] is True
        assert vr["entries"] == []

    def test_multiple_redactions_verified(self, text_pdf):
        """All redactions from a multi-term run are verified."""
        annots = get_suggestion_annotations(text_pdf, ["John Smith", "123-45-6789"])
        result = apply_redactions(text_pdf, annots["xfdf"])

        vr = verify_redactions(result["pdf_data"], result["redaction_log"])
        assert vr["all_passed"] is True
        assert len(vr["entries"]) >= 2

    def test_invalid_pdf_raises(self):
        with pytest.raises(ValueError, match="Invalid or corrupt PDF"):
            verify_redactions(
                b"not a pdf",
                [{"redaction_id": "x", "page": 0, "x0": 0, "y0": 0, "x1": 1, "y1": 1}],
            )

    def test_empty_pdf_raises(self):
        with pytest.raises(ValueError, match="Empty PDF data"):
            verify_redactions(
                b"",
                [{"redaction_id": "x", "page": 0, "x0": 0, "y0": 0, "x1": 1, "y1": 1}],
            )

    def test_second_pass_redaction_passes(self, text_pdf):
        """Multi-pass redactions should all pass verification."""
        style = {
            "fill_color": "#005941",
            "text_color": "#FFFFFF",
        }
        # First pass
        a1 = get_suggestion_annotations(text_pdf, ["John Smith"])
        r1 = apply_redactions(text_pdf, a1["xfdf"], style_config=style)

        # Second pass on already-redacted PDF
        a2 = get_suggestion_annotations(r1["pdf_data"], ["123-45-6789"])
        r2 = apply_redactions(r1["pdf_data"], a2["xfdf"], style_config=style)

        # Verify second pass redactions
        vr = verify_redactions(r2["pdf_data"], r2["redaction_log"])
        assert vr["all_passed"] is True
