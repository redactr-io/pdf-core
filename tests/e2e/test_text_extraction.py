import grpc
import pytest

from pdf_service.generated.redactr.pdf.v1 import pdf_service_pb2 as pb2


class TestExtractText:
    def test_extracts_text(self, stub, text_pdf):
        pages = list(stub.ExtractText(pb2.ExtractTextRequest(pdf_data=text_pdf)))
        assert len(pages) == 1
        assert "John Smith" in pages[0].text

    def test_specific_pages(self, stub, multi_page_pdf):
        pages = list(stub.ExtractText(
            pb2.ExtractTextRequest(pdf_data=multi_page_pdf, pages=[1])
        ))
        assert len(pages) == 1
        assert pages[0].page_number == 1

    def test_with_positions(self, stub, text_pdf):
        pages = list(stub.ExtractText(
            pb2.ExtractTextRequest(pdf_data=text_pdf, include_word_positions=True)
        ))
        assert len(pages[0].blocks) > 0

    def test_invalid_input(self, stub):
        with pytest.raises(grpc.RpcError) as exc_info:
            list(stub.ExtractText(pb2.ExtractTextRequest(pdf_data=b"bad")))
        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
