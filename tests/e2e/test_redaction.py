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

    def test_returns_redaction_log(self, stub, text_pdf):
        annot_response = stub.GetSuggestionAnnotations(
            pb2.GetSuggestionAnnotationsRequest(
                pdf_data=text_pdf,
                texts=["John Smith"],
            )
        )
        response = stub.ApplyRedactions(
            pb2.ApplyRedactionsRequest(
                pdf_data=text_pdf,
                xfdf=annot_response.xfdf,
            )
        )
        assert len(response.redaction_log) >= 1
        entry = response.redaction_log[0]
        assert len(entry.redaction_id) == 12
        assert entry.page == 0

    def test_with_redaction_style(self, stub, text_pdf):
        annot_response = stub.GetSuggestionAnnotations(
            pb2.GetSuggestionAnnotationsRequest(
                pdf_data=text_pdf,
                texts=["John Smith"],
            )
        )
        response = stub.ApplyRedactions(
            pb2.ApplyRedactionsRequest(
                pdf_data=text_pdf,
                xfdf=annot_response.xfdf,
                style=pb2.RedactionStyle(
                    fill_color="#005941",
                    text_color="#FFFFFF",
                ),
            )
        )
        assert response.redactions_applied >= 1
        assert len(response.pdf_data) > 0
        assert len(response.redaction_log) >= 1

    def test_invalid_pdf(self, stub):
        with pytest.raises(grpc.RpcError) as exc_info:
            stub.ApplyRedactions(
                pb2.ApplyRedactionsRequest(
                    pdf_data=b"bad",
                    xfdf="<xfdf/>",
                )
            )
        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
