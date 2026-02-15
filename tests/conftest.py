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
    doc.save(tmp_path, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="user", owner_pw="owner", permissions=perm)
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
