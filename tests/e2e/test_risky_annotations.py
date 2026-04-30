import grpc
import pytest

from pdf_service.generated.redactr.pdf.v1 import pdf_service_pb2 as pb2


class TestDetectRiskyAnnotations:
    def test_detects_filled_square_over_text(
        self, stub, pdf_with_filled_square_over_text
    ):
        response = stub.DetectRiskyAnnotations(
            pb2.DetectRiskyAnnotationsRequest(
                pdf_data=pdf_with_filled_square_over_text,
            )
        )

        assert response.total_findings == 1
        finding = response.findings[0]
        assert finding.source_subtype == "Square"
        assert finding.has_residual_text is True
        assert finding.has_residual_images is False
        assert len(finding.annotation_id) == 12

    def test_detects_ink_over_text(self, stub, pdf_with_ink_over_text):
        response = stub.DetectRiskyAnnotations(
            pb2.DetectRiskyAnnotationsRequest(
                pdf_data=pdf_with_ink_over_text,
            )
        )

        assert response.total_findings == 1
        assert response.findings[0].source_subtype == "Ink"

    def test_pdf_with_no_annotations_returns_empty(self, stub, text_pdf):
        response = stub.DetectRiskyAnnotations(
            pb2.DetectRiskyAnnotationsRequest(
                pdf_data=text_pdf,
            )
        )
        assert response.total_findings == 0
        assert list(response.findings) == []

    def test_invalid_pdf_returns_invalid_argument(self, stub):
        with pytest.raises(grpc.RpcError) as exc_info:
            stub.DetectRiskyAnnotations(
                pb2.DetectRiskyAnnotationsRequest(
                    pdf_data=b"%PDF-not-actually-a-pdf",
                )
            )
        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT

    def test_empty_pdf_returns_invalid_argument(self, stub):
        with pytest.raises(grpc.RpcError) as exc_info:
            stub.DetectRiskyAnnotations(pb2.DetectRiskyAnnotationsRequest(pdf_data=b""))
        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
