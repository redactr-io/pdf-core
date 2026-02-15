import os
from dataclasses import dataclass, field


@dataclass
class ServiceConfig:
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "50051")))
    max_workers: int = field(default_factory=lambda: int(os.getenv("MAX_WORKERS", "10")))
    max_message_size: int = field(
        default_factory=lambda: int(os.getenv("MAX_MESSAGE_SIZE", str(50 * 1024 * 1024)))
    )
    ocr_default_language: str = field(
        default_factory=lambda: os.getenv("OCR_DEFAULT_LANGUAGE", "eng")
    )
