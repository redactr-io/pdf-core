import grpc
import pytest

from pdf_service.generated.redactr.pdf.v1 import pdf_service_pb2 as pb2


class TestGetDocumentInfo:
    def test_returns_page_count(self, stub, text_pdf):
        response = stub.GetDocumentInfo(pb2.PdfInput(pdf_data=text_pdf))
        assert response.page_count == 1

    def test_multi_page(self, stub, multi_page_pdf):
        response = stub.GetDocumentInfo(pb2.PdfInput(pdf_data=multi_page_pdf))
        assert response.page_count == 3

    def test_detects_text_content(self, stub, text_pdf):
        response = stub.GetDocumentInfo(pb2.PdfInput(pdf_data=text_pdf))
        assert response.has_text_content is True

    def test_page_info(self, stub, text_pdf):
        response = stub.GetDocumentInfo(pb2.PdfInput(pdf_data=text_pdf))
        assert len(response.pages) == 1
        assert response.pages[0].width > 0
        assert response.pages[0].height > 0

    def test_invalid_input(self, stub):
        with pytest.raises(grpc.RpcError) as exc_info:
            stub.GetDocumentInfo(pb2.PdfInput(pdf_data=b"not a pdf"))
        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT

    def test_empty_input(self, stub):
        with pytest.raises(grpc.RpcError) as exc_info:
            stub.GetDocumentInfo(pb2.PdfInput(pdf_data=b""))
        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
