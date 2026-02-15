import xml.etree.ElementTree as ET

import grpc
import pytest

from pdf_service.generated.redactr.pdf.v1 import pdf_service_pb2 as pb2


class TestGetSuggestionAnnotations:
    def test_returns_xfdf(self, stub, text_pdf):
        response = stub.GetSuggestionAnnotations(
            pb2.GetSuggestionAnnotationsRequest(
                pdf_data=text_pdf,
                texts=["John Smith"],
            )
        )
        assert response.total_suggestions >= 1
        assert len(response.xfdf) > 0
        # Should be valid XML
        ET.fromstring(response.xfdf)

    def test_multiple_texts(self, stub, text_pdf):
        response = stub.GetSuggestionAnnotations(
            pb2.GetSuggestionAnnotationsRequest(
                pdf_data=text_pdf,
                texts=["John Smith", "123-45-6789"],
            )
        )
        assert response.total_suggestions >= 2

    def test_no_match(self, stub, text_pdf):
        response = stub.GetSuggestionAnnotations(
            pb2.GetSuggestionAnnotationsRequest(
                pdf_data=text_pdf,
                texts=["nonexistent"],
            )
        )
        assert response.total_suggestions == 0

    def test_invalid_input(self, stub):
        with pytest.raises(grpc.RpcError) as exc_info:
            stub.GetSuggestionAnnotations(
                pb2.GetSuggestionAnnotationsRequest(
                    pdf_data=b"bad",
                    texts=["test"],
                )
            )
        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
