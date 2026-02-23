import hashlib
import xml.etree.ElementTree as ET

import fitz
import pytest

from pdf_service.core.annotation import get_suggestion_annotations
from pdf_service.core.redaction import apply_redactions


class TestApplyRedactions:
    def test_removes_targeted_text(self, text_pdf):
        annots = get_suggestion_annotations(text_pdf, ["John Smith"])
        result = apply_redactions(text_pdf, annots["xfdf"])

        doc = fitz.open(stream=result["pdf_data"], filetype="pdf")
        text = doc[0].get_text()
        assert "John Smith" not in text
        doc.close()

    def test_non_targeted_text_survives(self, text_pdf):
        annots = get_suggestion_annotations(text_pdf, ["John Smith"])
        result = apply_redactions(text_pdf, annots["xfdf"])

        doc = fitz.open(stream=result["pdf_data"], filetype="pdf")
        text = doc[0].get_text()
        assert "123-45-6789" in text
        doc.close()

    def test_returns_correct_redaction_count(self, text_pdf):
        annots = get_suggestion_annotations(text_pdf, ["John Smith", "123-45-6789"])
        result = apply_redactions(text_pdf, annots["xfdf"])
        assert result["redactions_applied"] >= 2

    def test_returns_sha256_hash(self, text_pdf):
        annots = get_suggestion_annotations(text_pdf, ["John Smith"])
        result = apply_redactions(text_pdf, annots["xfdf"])
        expected_hash = hashlib.sha256(result["pdf_data"]).digest()
        assert result["content_hash"] == expected_hash

    def test_selective_redaction(self, text_pdf):
        """Only redact a subset of suggestions by filtering the XFDF."""
        annots = get_suggestion_annotations(text_pdf, ["John Smith", "123-45-6789"])
        # Parse and keep only the first highlight (John Smith)
        root = ET.fromstring(annots["xfdf"])
        ns = "http://ns.adobe.com/xfdf/"
        annots_el = root.find(f"{{{ns}}}annots")
        if annots_el is None:
            annots_el = root.find("annots")
        highlights = annots_el.findall(f"{{{ns}}}highlight")
        if not highlights:
            highlights = annots_el.findall("highlight")

        # Keep only highlights whose contents match "John Smith"
        for hl in highlights:
            contents = hl.find(f"{{{ns}}}contents")
            if contents is None:
                contents = hl.find("contents")
            if contents is not None and contents.text != "John Smith":
                annots_el.remove(hl)

        filtered_xfdf = ET.tostring(root, encoding="unicode", xml_declaration=True)
        result = apply_redactions(text_pdf, filtered_xfdf)

        doc = fitz.open(stream=result["pdf_data"], filetype="pdf")
        text = doc[0].get_text()
        assert "John Smith" not in text
        assert "123-45-6789" in text  # SSN should survive
        doc.close()

    def test_garbage_collection_removes_redacted_bytes(self, text_pdf):
        annots = get_suggestion_annotations(text_pdf, ["John Smith"])
        result = apply_redactions(text_pdf, annots["xfdf"])
        assert b"John Smith" not in result["pdf_data"]

    def test_sets_producer_metadata(self, text_pdf):
        annots = get_suggestion_annotations(text_pdf, ["John Smith"])
        result = apply_redactions(text_pdf, annots["xfdf"])

        doc = fitz.open(stream=result["pdf_data"], filetype="pdf")
        assert doc.metadata["producer"].startswith("PDF Core ")
        assert "by redactr.io" in doc.metadata["producer"]
        doc.close()

    def test_raises_for_empty_pdf_bytes(self):
        with pytest.raises(ValueError, match="Empty PDF data"):
            apply_redactions(b"", "<xfdf/>")

    def test_raises_for_empty_xfdf(self, text_pdf):
        with pytest.raises(ValueError, match="Empty XFDF data"):
            apply_redactions(text_pdf, "")

    def test_raises_for_corrupt_pdf(self):
        with pytest.raises(ValueError, match="Invalid or corrupt PDF"):
            apply_redactions(b"not a pdf", "<xfdf/>")

    def test_output_contains_redact_annotations(self, text_pdf):
        annots = get_suggestion_annotations(text_pdf, ["John Smith"])
        result = apply_redactions(text_pdf, annots["xfdf"])

        doc = fitz.open(stream=result["pdf_data"], filetype="pdf")
        page = doc[0]
        redacts = [a for a in (page.annots() or []) if a.type[1] == "Redact"]
        assert len(redacts) >= 1
        doc.close()

    def test_raises_for_malformed_xfdf(self, text_pdf):
        with pytest.raises(ValueError, match="Malformed XFDF"):
            apply_redactions(text_pdf, "<<<not xml>>>")

    def test_redaction_log_returned(self, text_pdf):
        annots = get_suggestion_annotations(text_pdf, ["John Smith"])
        result = apply_redactions(text_pdf, annots["xfdf"])
        assert "redaction_log" in result
        assert len(result["redaction_log"]) >= 1
        entry = result["redaction_log"][0]
        assert "redaction_id" in entry
        assert "page" in entry
        assert "x0" in entry
        assert "y0" in entry
        assert "x1" in entry
        assert "y1" in entry

    def test_redaction_log_deterministic_ids(self, text_pdf):
        annots = get_suggestion_annotations(text_pdf, ["John Smith"])
        result1 = apply_redactions(text_pdf, annots["xfdf"])
        result2 = apply_redactions(text_pdf, annots["xfdf"])
        ids1 = [e["redaction_id"] for e in result1["redaction_log"]]
        ids2 = [e["redaction_id"] for e in result2["redaction_log"]]
        assert ids1 == ids2

    def test_style_none_preserves_behavior(self, text_pdf):
        annots = get_suggestion_annotations(text_pdf, ["John Smith"])
        result = apply_redactions(text_pdf, annots["xfdf"], style_config=None)
        assert result["redactions_applied"] >= 1
        # No branding drawn — just the standard Redact annotations
        doc = fitz.open(stream=result["pdf_data"], filetype="pdf")
        page = doc[0]
        redacts = [a for a in (page.annots() or []) if a.type[1] == "Redact"]
        assert len(redacts) >= 1
        doc.close()

    def test_style_config_changes_fill(self, text_pdf):
        annots = get_suggestion_annotations(text_pdf, ["John Smith"])
        style = {"fill_color": "#005941"}
        result = apply_redactions(text_pdf, annots["xfdf"], style_config=style)
        assert result["redactions_applied"] >= 1
        # Branding should have drawn something on the page
        doc = fitz.open(stream=result["pdf_data"], filetype="pdf")
        page = doc[0]
        drawings = page.get_drawings()
        assert len(drawings) >= 1
        doc.close()
