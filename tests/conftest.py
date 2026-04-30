import fitz
import pytest

SENSITIVE_TEXT = (
    "Name: John Smith\n"
    "SSN: 123-45-6789\n"
    "Email: john.smith@example.com\n"
    "Phone: (555) 123-4567\n"
)

PAGE2_TEXT = "This is page two with different content about Project Alpha."
PAGE3_TEXT = "Page three contains financial data: $50,000 salary."


@pytest.fixture
def text_pdf() -> bytes:
    """Single page PDF with known sensitive data."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), SENSITIVE_TEXT, fontsize=12)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def multi_page_pdf() -> bytes:
    """3 pages with different content on each."""
    doc = fitz.open()

    page1 = doc.new_page()
    page1.insert_text((72, 72), SENSITIVE_TEXT, fontsize=12)

    page2 = doc.new_page()
    page2.insert_text((72, 72), PAGE2_TEXT, fontsize=12)

    page3 = doc.new_page()
    page3.insert_text((72, 72), PAGE3_TEXT, fontsize=12)

    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def scanned_pdf() -> bytes:
    """Single page with a large image, no text layer."""
    doc = fitz.open()
    page = doc.new_page()

    # Create a simple image (100x100 red pixel block as PNG)
    import struct
    import zlib

    width, height = 100, 100
    raw_data = b""
    for _ in range(height):
        raw_data += b"\x00"  # filter byte
        raw_data += b"\xff\x00\x00" * width  # RGB red pixels

    def png_chunk(chunk_type, data):
        c = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc

    png = b"\x89PNG\r\n\x1a\n"
    png += png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += png_chunk(b"IDAT", zlib.compress(raw_data))
    png += png_chunk(b"IEND", b"")

    page.insert_image(fitz.Rect(0, 0, 400, 400), stream=png)

    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def mixed_pdf() -> bytes:
    """2 pages: one text, one scanned (image only)."""
    doc = fitz.open()

    # Page 1: text
    page1 = doc.new_page()
    page1.insert_text((72, 72), SENSITIVE_TEXT, fontsize=12)

    # Page 2: image only
    page2 = doc.new_page()
    import struct
    import zlib

    width, height = 50, 50
    raw_data = b""
    for _ in range(height):
        raw_data += b"\x00"
        raw_data += b"\x00\x00\xff" * width

    def png_chunk(chunk_type, data):
        c = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc

    png = b"\x89PNG\r\n\x1a\n"
    png += png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += png_chunk(b"IDAT", zlib.compress(raw_data))
    png += png_chunk(b"IEND", b"")

    page2.insert_image(fitz.Rect(0, 0, 200, 200), stream=png)

    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def suggestion_xfdf(text_pdf) -> str:
    """XFDF with highlight suggestions for John Smith."""
    from pdf_service.core.annotation import get_suggestion_annotations

    result = get_suggestion_annotations(text_pdf, ["John Smith"])
    return result["xfdf"]


@pytest.fixture
def encrypted_pdf() -> bytes:
    """PDF encrypted with a password."""
    import tempfile

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Secret content", fontsize=12)
    perm = fitz.PDF_PERM_ACCESSIBILITY
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name
    doc.save(
        tmp_path,
        encryption=fitz.PDF_ENCRYPT_AES_256,
        user_pw="user",
        owner_pw="owner",
        permissions=perm,
    )
    doc.close()
    import os

    with open(tmp_path, "rb") as f:
        data = f.read()
    os.unlink(tmp_path)
    return data


@pytest.fixture
def empty_pdf() -> bytes:
    """Valid PDF with a single blank page."""
    doc = fitz.open()
    doc.new_page()
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def large_text_pdf() -> bytes:
    """50+ pages for performance baseline."""
    doc = fitz.open()
    for i in range(50):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i + 1} content. " * 20, fontsize=10)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def pdf_with_filled_square_over_text() -> bytes:
    """Single page PDF with text and a filled black Square annotation
    covering the first line of text (no /AP appearance stream — this is
    the source-of-truth case where pdf.js drops /IC).
    """
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "BURIED SECRET DATA", fontsize=14)
    annot = page.add_rect_annot(fitz.Rect(70, 88, 220, 112))
    annot.set_colors(stroke=(0, 0, 0), fill=(0, 0, 0))
    annot.set_border(width=1)
    annot.update()
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def pdf_with_unfilled_square_over_text() -> bytes:
    """Same as above but the Square has no fill — should NOT be flagged."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "BURIED SECRET DATA", fontsize=14)
    annot = page.add_rect_annot(fitz.Rect(70, 88, 220, 112))
    annot.set_colors(stroke=(0, 0, 0))  # no fill
    annot.set_border(width=1)
    annot.update()
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def pdf_with_filled_square_over_whitespace() -> bytes:
    """Filled Square with no text or image underneath — should NOT be flagged."""
    doc = fitz.open()
    page = doc.new_page()
    annot = page.add_rect_annot(fitz.Rect(300, 300, 400, 350))
    annot.set_colors(stroke=(0, 0, 0), fill=(0, 0, 0))
    annot.set_border(width=1)
    annot.update()
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def pdf_with_ink_over_text() -> bytes:
    """Ink annotation (a single jagged stroke) drawn over text."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "BURIED SECRET DATA", fontsize=14)
    inks = [
        [
            (75, 95),
            (110, 105),
            (140, 95),
            (170, 105),
            (200, 95),
            (215, 105),
        ]
    ]
    annot = page.add_ink_annot(inks)
    annot.set_colors(stroke=(0, 0, 0))
    annot.set_border(width=1)
    annot.update()
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def pdf_with_highlight_over_text() -> bytes:
    """Highlight annotation over text — out of scope, should NOT be flagged."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "BURIED SECRET DATA", fontsize=14)
    rects = page.search_for("BURIED SECRET DATA")
    if rects:
        page.add_highlight_annot(rects[0])
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def pdf_with_filled_circle_over_text() -> bytes:
    """Filled Circle annotation over text."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "BURIED SECRET DATA", fontsize=14)
    annot = page.add_circle_annot(fitz.Rect(70, 88, 220, 112))
    annot.set_colors(stroke=(0, 0, 0), fill=(0, 0, 0))
    annot.set_border(width=1)
    annot.update()
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def pdf_with_filled_polygon_over_text() -> bytes:
    """Filled Polygon annotation over text."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "BURIED SECRET DATA", fontsize=14)
    points = [(70, 90), (220, 90), (220, 112), (70, 112)]
    annot = page.add_polygon_annot(points)
    annot.set_colors(stroke=(0, 0, 0), fill=(0, 0, 0))
    annot.set_border(width=1)
    annot.update()
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def pdf_with_ink_over_whitespace() -> bytes:
    """Ink annotation drawn over a blank area — should NOT be flagged."""
    doc = fitz.open()
    page = doc.new_page()
    inks = [
        [
            (300, 300),
            (335, 310),
            (365, 300),
            (395, 310),
        ]
    ]
    annot = page.add_ink_annot(inks)
    annot.set_colors(stroke=(0, 0, 0))
    annot.set_border(width=1)
    annot.update()
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def pdf_with_filled_square_over_image() -> bytes:
    """Filled black Square covering a small embedded image — should be
    flagged via `has_residual_images`. Uses the same hand-built PNG recipe
    as `scanned_pdf` so we don't pull in extra dependencies.
    """
    import struct
    import zlib

    width, height = 50, 50
    raw = b""
    for _ in range(height):
        raw += b"\x00"  # filter byte
        raw += b"\x80\x40\x20" * width  # arbitrary opaque RGB

    def _chunk(tag: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(tag + payload).to_bytes(4, "big")
        return len(payload).to_bytes(4, "big") + tag + payload + crc

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    idat = zlib.compress(raw)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", idat)
        + _chunk(b"IEND", b"")
    )

    doc = fitz.open()
    page = doc.new_page()
    page.insert_image(fitz.Rect(80, 90, 130, 140), stream=png)
    annot = page.add_rect_annot(fitz.Rect(70, 88, 145, 145))
    annot.set_colors(stroke=(0, 0, 0), fill=(0, 0, 0))
    annot.set_border(width=1)
    annot.update()
    data = doc.tobytes()
    doc.close()
    return data
