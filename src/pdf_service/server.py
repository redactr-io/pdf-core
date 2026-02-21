import logging
import signal
from concurrent import futures

import grpc
from grpc_health.v1 import health, health_pb2, health_pb2_grpc
from grpc_reflection.v1alpha import reflection

from pdf_service.config import ServiceConfig
from pdf_service.generated.redactr.pdf.v1 import pdf_service_pb2, pdf_service_pb2_grpc
from pdf_service.grpc.servicer import PdfServiceServicer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def serve():
    config = ServiceConfig()

    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=config.max_workers),
        options=[
            ("grpc.max_send_message_length", config.max_message_size),
            ("grpc.max_receive_message_length", config.max_message_size),
        ],
    )

    # Register PDF service
    pdf_service_pb2_grpc.add_PdfServiceServicer_to_server(PdfServiceServicer(), server)

    # Health checking
    health_servicer = health.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
    health_servicer.set(
        "redactr.pdf.v1.PdfService",
        health_pb2.HealthCheckResponse.SERVING,
    )

    # Reflection
    service_names = (
        pdf_service_pb2.DESCRIPTOR.services_by_name["PdfService"].full_name,
        reflection.SERVICE_NAME,
        health.SERVICE_NAME,
    )
    reflection.enable_server_reflection(service_names, server)

    listen_addr = f"[::]:{config.port}"
    server.add_insecure_port(listen_addr)
    server.start()
    logger.info("pdf-core gRPC server listening on %s", listen_addr)

    # Graceful shutdown
    def shutdown(signum, frame):
        logger.info("Received signal %s, shutting down...", signum)
        health_servicer.set(
            "redactr.pdf.v1.PdfService",
            health_pb2.HealthCheckResponse.NOT_SERVING,
        )
        server.stop(grace=5)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    server.wait_for_termination()


if __name__ == "__main__":
    serve()
