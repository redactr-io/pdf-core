"""Tests for the MergePdfs RPC."""

import pymupdf

from pdf_service.generated.redactr.pdf.v1 import pdf_service_pb2
from pdf_service.grpc.servicer import PdfServiceServicer


def _make_pdf(text: str) -> bytes:
    """Create a single-page PDF containing the given text."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    out = doc.tobytes()
    doc.close()
    return out


def test_merge_pdfs_combines_two_documents():
    pdf_a = _make_pdf("Document A")
    pdf_b = _make_pdf("Document B")

    servicer = PdfServiceServicer()
    request = pdf_service_pb2.MergePdfsRequest(pdfs=[pdf_a, pdf_b])
    response = servicer.MergePdfs(request, context=None)

    assert response.page_count == 2
    merged = pymupdf.open(stream=response.pdf_data, filetype="pdf")
    assert len(merged) == 2
    assert "Document A" in merged[0].get_text()
    assert "Document B" in merged[1].get_text()
    merged.close()


def test_merge_pdfs_preserves_order():
    pdfs = [_make_pdf(f"Page {i}") for i in range(5)]

    servicer = PdfServiceServicer()
    request = pdf_service_pb2.MergePdfsRequest(pdfs=pdfs)
    response = servicer.MergePdfs(request, context=None)

    assert response.page_count == 5
    merged = pymupdf.open(stream=response.pdf_data, filetype="pdf")
    for i in range(5):
        assert f"Page {i}" in merged[i].get_text()
    merged.close()


def test_merge_pdfs_empty_input_raises():
    servicer = PdfServiceServicer()
    request = pdf_service_pb2.MergePdfsRequest(pdfs=[])

    import pytest

    with pytest.raises(ValueError, match="at least one PDF required"):
        servicer.MergePdfs(request, context=None)
