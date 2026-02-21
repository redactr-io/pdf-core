from typing import TypedDict


class PageInfoResult(TypedDict):
    page_number: int
    has_text: bool
    has_images: bool
    likely_scanned: bool
    width: float
    height: float


class DocumentMetadataResult(TypedDict):
    title: str
    author: str
    producer: str
    creator: str


class DocumentInfoResult(TypedDict):
    page_count: int
    file_size_bytes: int
    is_encrypted: bool
    has_text_content: bool
    has_annotations: bool
    existing_annotation_count: int
    metadata: DocumentMetadataResult
    pages: list[PageInfoResult]


class TextBlockResult(TypedDict):
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    block_number: int
    line_number: int


class PageTextResult(TypedDict):
    page_number: int
    text: str
    blocks: list[TextBlockResult]


class SuggestionResultItem(TypedDict):
    text: str
    page: int
    occurrences_found: int


class SuggestionAnnotationsResult(TypedDict):
    xfdf: str
    total_suggestions: int
    results: list[SuggestionResultItem]


class RedactionResult(TypedDict):
    pdf_data: bytes
    redactions_applied: int
    content_hash: bytes
