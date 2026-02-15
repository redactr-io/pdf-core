import os

import grpc
import pytest

from pdf_service.generated.redactr.pdf.v1 import pdf_service_pb2_grpc


@pytest.fixture(scope="session")
def stub():
    host = os.environ.get("PDF_SERVICE_HOST", "localhost:50051")
    channel = grpc.insecure_channel(
        host,
        options=[
            ("grpc.max_send_message_length", 50 * 1024 * 1024),
            ("grpc.max_receive_message_length", 50 * 1024 * 1024),
        ],
    )
    # Wait for channel to be ready
    grpc.channel_ready_future(channel).result(timeout=30)
    return pdf_service_pb2_grpc.PdfServiceStub(channel)
