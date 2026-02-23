from __future__ import annotations

from typing import TYPE_CHECKING

import grpc

from pdf_service.core import annotation, document_info, redaction, text_extraction
from pdf_service.generated.redactr.pdf.v1 import pdf_service_pb2 as pb2
from pdf_service.generated.redactr.pdf.v1 import pdf_service_pb2_grpc as pb2_grpc

if TYPE_CHECKING:
    from pdf_service.core.types import RedactionStyleConfig


class PdfServiceServicer(pb2_grpc.PdfServiceServicer):
    def GetDocumentInfo(self, request, context):
        try:
            result = document_info.get_document_info(request.pdf_data)
        except ValueError as e:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))
            return
        except Exception as e:
            context.abort(grpc.StatusCode.INTERNAL, f"Processing failed: {e}")
            return

        meta = result["metadata"]
        pages = [
            pb2.PageInfo(
                page_number=p["page_number"],
                has_text=p["has_text"],
                has_images=p["has_images"],
                likely_scanned=p["likely_scanned"],
                width=p["width"],
                height=p["height"],
            )
            for p in result["pages"]
        ]

        return pb2.DocumentInfoResponse(
            page_count=result["page_count"],
            file_size_bytes=result["file_size_bytes"],
            is_encrypted=result["is_encrypted"],
            has_text_content=result["has_text_content"],
            has_annotations=result["has_annotations"],
            existing_annotation_count=result["existing_annotation_count"],
            metadata=pb2.DocumentMetadata(
                title=meta["title"],
                author=meta["author"],
                producer=meta["producer"],
                creator=meta["creator"],
            ),
            pages=pages,
        )

    def ExtractText(self, request, context):
        pages = list(request.pages) if request.pages else None
        ocr_options = None
        if request.HasField("ocr"):
            ocr_options = {
                "enabled": request.ocr.enabled,
                "language": request.ocr.language or "eng",
                "force": request.ocr.force,
            }

        try:
            for page_result in text_extraction.extract_text(
                request.pdf_data,
                pages,
                request.include_word_positions,
                ocr_options,
            ):
                blocks = [
                    pb2.TextBlock(
                        text=b["text"],
                        x0=b["x0"],
                        y0=b["y0"],
                        x1=b["x1"],
                        y1=b["y1"],
                        block_number=b["block_number"],
                        line_number=b["line_number"],
                    )
                    for b in page_result["blocks"]
                ]
                yield pb2.PageTextResponse(
                    page_number=page_result["page_number"],
                    text=page_result["text"],
                    blocks=blocks,
                )
        except ValueError as e:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))
        except Exception as e:
            context.abort(grpc.StatusCode.INTERNAL, f"Processing failed: {e}")

    def GetSuggestionAnnotations(self, request, context):
        try:
            result = annotation.get_suggestion_annotations(
                request.pdf_data, list(request.texts)
            )
        except ValueError as e:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))
            return
        except Exception as e:
            context.abort(grpc.StatusCode.INTERNAL, f"Processing failed: {e}")
            return

        results = [
            pb2.SuggestionResult(
                text=r["text"],
                page=r["page"],
                occurrences_found=r["occurrences_found"],
            )
            for r in result["results"]
        ]

        return pb2.GetSuggestionAnnotationsResponse(
            xfdf=result["xfdf"],
            total_suggestions=result["total_suggestions"],
            results=results,
        )

    def ApplyRedactions(self, request, context):
        style_config: RedactionStyleConfig | None = None
        if request.HasField("style"):
            s = request.style
            sc: RedactionStyleConfig = {}
            if s.fill_color:
                sc["fill_color"] = s.fill_color
            if s.border_color:
                sc["border_color"] = s.border_color
            if s.text_color:
                sc["text_color"] = s.text_color
            if s.icon_png:
                sc["icon_png"] = s.icon_png
            if s.label_prefix:
                sc["label_prefix"] = s.label_prefix
            style_config = sc

        try:
            result = redaction.apply_redactions(
                request.pdf_data, request.xfdf, style_config=style_config
            )
        except ValueError as e:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))
            return
        except Exception as e:
            context.abort(grpc.StatusCode.INTERNAL, f"Processing failed: {e}")
            return

        log_entries = [
            pb2.RedactionLogEntry(
                redaction_id=entry["redaction_id"],
                page=entry["page"],
                x0=entry["x0"],
                y0=entry["y0"],
                x1=entry["x1"],
                y1=entry["y1"],
            )
            for entry in result["redaction_log"]
        ]

        return pb2.ApplyRedactionsResponse(
            pdf_data=result["pdf_data"],
            redactions_applied=result["redactions_applied"],
            content_hash=result["content_hash"],
            redaction_log=log_entries,
        )
