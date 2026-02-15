import grpc
import pytest

from pdf_service.generated.redactr.pdf.v1 import pdf_service_pb2 as pb2


class TestFullFlow:
    def test_suggestion_then_redact_flow(self, stub, text_pdf):
        """GetSuggestionAnnotations → ApplyRedactions → ExtractText to verify removal."""
        # Step 1: Get suggestion annotations
        annot_response = stub.GetSuggestionAnnotations(
            pb2.GetSuggestionAnnotationsRequest(
                pdf_data=text_pdf,
                texts=["John Smith", "123-45-6789"],
            )
        )
        assert annot_response.total_suggestions >= 2

        # Step 2: Apply redactions with the XFDF
        redact_response = stub.ApplyRedactions(
            pb2.ApplyRedactionsRequest(
                pdf_data=text_pdf,
                xfdf=annot_response.xfdf,
            )
        )
        assert redact_response.redactions_applied >= 2

        # Step 3: Verify content is removed
        pages = list(stub.ExtractText(
            pb2.ExtractTextRequest(pdf_data=redact_response.pdf_data)
        ))
        text = pages[0].text
        assert "John Smith" not in text
        assert "123-45-6789" not in text
        # Other content should survive
        assert "Email" in text or "Phone" in text

    def test_round_trip_integrity(self, stub, text_pdf):
        """PDF bytes survive the full journey without corruption."""
        info1 = stub.GetDocumentInfo(pb2.PdfInput(pdf_data=text_pdf))

        annot_response = stub.GetSuggestionAnnotations(
            pb2.GetSuggestionAnnotationsRequest(
                pdf_data=text_pdf,
                texts=["John Smith"],
            )
        )

        redact_response = stub.ApplyRedactions(
            pb2.ApplyRedactionsRequest(
                pdf_data=text_pdf,
                xfdf=annot_response.xfdf,
            )
        )
        info2 = stub.GetDocumentInfo(
            pb2.PdfInput(pdf_data=redact_response.pdf_data)
        )
        assert info2.page_count == info1.page_count

    def test_error_propagation(self, stub):
        """Invalid input returns correct gRPC status codes."""
        with pytest.raises(grpc.RpcError) as exc_info:
            stub.GetDocumentInfo(pb2.PdfInput(pdf_data=b""))
        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT

        with pytest.raises(grpc.RpcError) as exc_info:
            list(stub.ExtractText(pb2.ExtractTextRequest(pdf_data=b"bad")))
        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT

        with pytest.raises(grpc.RpcError) as exc_info:
            stub.GetSuggestionAnnotations(
                pb2.GetSuggestionAnnotationsRequest(
                    pdf_data=b"bad",
                    texts=["x"],
                )
            )
        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
