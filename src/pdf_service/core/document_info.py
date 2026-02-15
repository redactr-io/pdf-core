import logging

import fitz

logger = logging.getLogger(__name__)


def get_document_info(pdf_data: bytes) -> dict:
    if not pdf_data:
        raise ValueError("Empty PDF data")

    try:
        doc = fitz.open(stream=pdf_data, filetype="pdf")
    except Exception:
        raise ValueError("Invalid or corrupt PDF")

    try:
        if doc.is_encrypted:
            raise ValueError("PDF is encrypted")

        has_text_content = False
        has_annotations = False
        annotation_count = 0
        pages = []

        for i, page in enumerate(doc):
            page_text = page.get_text().strip()
            page_has_text = bool(page_text)
            page_images = page.get_images()
            page_has_images = len(page_images) > 0

            if page_has_text:
                has_text_content = True

            page_annots = list(page.annots() or [])
            if page_annots:
                has_annotations = True
                annotation_count += len(page_annots)

            pages.append({
                "page_number": i,
                "has_text": page_has_text,
                "has_images": page_has_images,
                "likely_scanned": page_has_images and not page_has_text,
                "width": page.rect.width,
                "height": page.rect.height,
            })

        meta = doc.metadata or {}

        logger.info(
            "Analyzed %d-page document (%d bytes, %d annotations)",
            len(doc), len(pdf_data), annotation_count,
        )

        return {
            "page_count": len(doc),
            "file_size_bytes": len(pdf_data),
            "is_encrypted": doc.is_encrypted,
            "has_text_content": has_text_content,
            "has_annotations": has_annotations,
            "existing_annotation_count": annotation_count,
            "metadata": {
                "title": meta.get("title", ""),
                "author": meta.get("author", ""),
                "producer": meta.get("producer", ""),
                "creator": meta.get("creator", ""),
            },
            "pages": pages,
        }
    finally:
        doc.close()
