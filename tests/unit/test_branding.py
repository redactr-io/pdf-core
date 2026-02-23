import fitz
import pytest

from pdf_service.core.branding import (
    LARGE_MIN_HEIGHT,
    LARGE_MIN_WIDTH,
    MEDIUM_MIN_HEIGHT,
    MEDIUM_MIN_WIDTH,
    BrandingStyle,
    draw_branding,
    generate_redaction_id,
    hex_to_rgb,
)


class TestHexToRgb:
    def test_parses_black(self):
        assert hex_to_rgb("#000000") == (0.0, 0.0, 0.0)

    def test_parses_white(self):
        assert hex_to_rgb("#FFFFFF") == (1.0, 1.0, 1.0)

    def test_parses_color(self):
        r, g, b = hex_to_rgb("#005941")
        assert abs(r - 0.0) < 0.01
        assert abs(g - 0.349) < 0.01
        assert abs(b - 0.255) < 0.01

    def test_without_hash(self):
        assert hex_to_rgb("FF0000") == (1.0, 0.0, 0.0)

    def test_rejects_short(self):
        with pytest.raises(ValueError, match="Invalid hex color"):
            hex_to_rgb("#FFF")

    def test_rejects_invalid_chars(self):
        with pytest.raises(ValueError, match="Invalid hex color"):
            hex_to_rgb("#ZZZZZZ")


class TestGenerateRedactionId:
    def test_deterministic(self):
        id1 = generate_redaction_id(0, 10.0, 20.0, 100.0, 40.0)
        id2 = generate_redaction_id(0, 10.0, 20.0, 100.0, 40.0)
        assert id1 == id2

    def test_is_12_hex_chars(self):
        rid = generate_redaction_id(0, 10.0, 20.0, 100.0, 40.0)
        assert len(rid) == 12
        int(rid, 16)  # Should not raise

    def test_varies_by_page(self):
        id1 = generate_redaction_id(0, 10.0, 20.0, 100.0, 40.0)
        id2 = generate_redaction_id(1, 10.0, 20.0, 100.0, 40.0)
        assert id1 != id2

    def test_varies_by_coords(self):
        id1 = generate_redaction_id(0, 10.0, 20.0, 100.0, 40.0)
        id2 = generate_redaction_id(0, 10.0, 20.0, 100.0, 50.0)
        assert id1 != id2


class TestBrandingStyle:
    def test_from_config_none_returns_none(self):
        assert BrandingStyle.from_config(None) is None

    def test_from_config_defaults(self):
        style = BrandingStyle.from_config({})
        assert style is not None
        assert style.fill_color == (0.0, 0.0, 0.0)
        assert style.border_color == (0.0, 0.0, 0.0)  # Defaults to fill
        assert style.text_color == (1.0, 1.0, 1.0)
        assert style.icon_png is None
        assert style.label_prefix == "ID:"

    def test_from_config_overrides(self):
        style = BrandingStyle.from_config(
            {
                "fill_color": "#005941",
                "border_color": "#FF0000",
                "text_color": "#0000FF",
                "label_prefix": "ID:",
            }
        )
        assert style.fill_color == hex_to_rgb("#005941")
        assert style.border_color == hex_to_rgb("#FF0000")
        assert style.text_color == hex_to_rgb("#0000FF")
        assert style.label_prefix == "ID:"

    def test_border_defaults_to_fill(self):
        style = BrandingStyle.from_config({"fill_color": "#005941"})
        assert style.border_color == style.fill_color

    def test_is_frozen(self):
        style = BrandingStyle.from_config({})
        with pytest.raises(AttributeError):
            style.fill_color = (1.0, 0.0, 0.0)


class TestDrawBranding:
    """Test two-tier rendering by checking PyMuPDF drawing counts."""

    def _make_page(self):
        doc = fitz.open()
        page = doc.new_page()
        return doc, page

    def _default_style(self):
        return BrandingStyle.from_config({"fill_color": "#005941"})

    def _count_items(self, page, item_type):
        """Count drawing items of a given type (e.g. 're', 'l', 'c')."""
        count = 0
        for d in page.get_drawings():
            for item in d["items"]:
                if item[0] == item_type:
                    count += 1
        return count

    def test_small_rect_only_rounded_rect(self):
        """Small rects get a rounded rect with border, no text, no lines."""
        doc, page = self._make_page()
        rect = fitz.Rect(0, 0, MEDIUM_MIN_WIDTH - 1, MEDIUM_MIN_HEIGHT - 1)
        draw_branding(page, rect, "abc123def456", self._default_style())
        # Rounded rect is composed of lines + curves
        assert self._count_items(page, "l") >= 4  # sides
        assert self._count_items(page, "c") >= 4  # corners
        # No text annotations
        annots = list(page.annots() or [])
        assert len(annots) == 0
        doc.close()

    def test_medium_rect_has_id_text(self):
        """Medium rects show ID text at bottom-right, no cross lines."""
        doc, page = self._make_page()
        rect = fitz.Rect(0, 0, MEDIUM_MIN_WIDTH + 10, MEDIUM_MIN_HEIGHT + 5)
        draw_branding(page, rect, "abc123def456", self._default_style())
        annots = list(page.annots() or [])
        freetext = [a for a in annots if a.type[1] == "FreeText"]
        assert len(freetext) == 1
        assert "abc123def456" in freetext[0].info["content"]
        doc.close()

    def test_large_rect_has_text_bottom_right(self):
        """Large rects show right-aligned ID text near the bottom."""
        doc, page = self._make_page()
        rect = fitz.Rect(0, 0, LARGE_MIN_WIDTH + 50, LARGE_MIN_HEIGHT + 10)
        draw_branding(page, rect, "abc123def456", self._default_style())
        annots = list(page.annots() or [])
        freetext = [a for a in annots if a.type[1] == "FreeText"]
        assert len(freetext) >= 1
        assert "abc123def456" in freetext[0].info["content"]
        # Text rect should be at the bottom of the frame (flush with frame edge)
        text_annot_rect = freetext[0].rect
        assert text_annot_rect.y0 > rect.y0 + rect.height / 2  # in the bottom half
        doc.close()

    def test_icon_shown_on_all_sizes(self):
        """Icon is inserted at the top-left corner for any size redaction."""
        import struct
        import zlib

        # Minimal 1x1 red PNG
        raw_data = b"\x00\xff\x00\x00"
        png = b"\x89PNG\r\n\x1a\n"

        def chunk(t, d):
            c = t + d
            crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
            return struct.pack(">I", len(d)) + c + crc

        png += chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        png += chunk(b"IDAT", zlib.compress(raw_data))
        png += chunk(b"IEND", b"")

        style = BrandingStyle.from_config({"fill_color": "#005941", "icon_png": png})

        # Small rect — icon should still appear
        doc, page = self._make_page()
        rect = fitz.Rect(10, 20, 10 + MEDIUM_MIN_WIDTH - 1, 20 + MEDIUM_MIN_HEIGHT - 1)
        draw_branding(page, rect, "abc123def456", style)
        assert len(page.get_images()) >= 1
        doc.close()

        # Large rect — icon should appear
        doc, page = self._make_page()
        rect = fitz.Rect(10, 20, 10 + LARGE_MIN_WIDTH + 50, 20 + LARGE_MIN_HEIGHT + 10)
        draw_branding(page, rect, "abc123def456", style)
        assert len(page.get_images()) >= 1
        doc.close()

    def test_bad_icon_degrades_gracefully(self):
        style = BrandingStyle.from_config(
            {"fill_color": "#005941", "icon_png": b"not a png"}
        )
        doc, page = self._make_page()
        rect = fitz.Rect(0, 0, LARGE_MIN_WIDTH + 50, LARGE_MIN_HEIGHT + 10)
        # Should not raise
        draw_branding(page, rect, "abc123def456", style)
        doc.close()
