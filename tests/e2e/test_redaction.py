import grpc
import pytest

from pdf_service.generated.redactr.pdf.v1 import pdf_service_pb2 as pb2


class TestApplyRedactions:
    def test_applies_redactions_from_xfdf(self, stub, text_pdf):
        # Get suggestion annotations first
        annot_response = stub.GetSuggestionAnnotations(
            pb2.GetSuggestionAnnotationsRequest(
                pdf_data=text_pdf,
                texts=["John Smith"],
            )
        )
        # Apply redactions using the XFDF
        response = stub.ApplyRedactions(
            pb2.ApplyRedactionsRequest(
                pdf_data=text_pdf,
                xfdf=annot_response.xfdf,
            )
        )
        assert response.redactions_applied >= 1
        assert len(response.pdf_data) > 0
        assert len(response.content_hash) == 32  # SHA-256

    def test_no_highlights_in_xfdf(self, stub, text_pdf):
        # XFDF with no highlight elements
        empty_xfdf = '<?xml version="1.0" ?><xfdf xmlns="http://ns.adobe.com/xfdf/"><annots/></xfdf>'
        response = stub.ApplyRedactions(
            pb2.ApplyRedactionsRequest(
                pdf_data=text_pdf,
                xfdf=empty_xfdf,
            )
        )
        assert response.redactions_applied == 0

    def test_invalid_pdf(self, stub):
        with pytest.raises(grpc.RpcError) as exc_info:
            stub.ApplyRedactions(
                pb2.ApplyRedactionsRequest(
                    pdf_data=b"bad",
                    xfdf="<xfdf/>",
                )
            )
        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
