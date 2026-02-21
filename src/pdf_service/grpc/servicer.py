import grpc

from pdf_service.core import annotation, document_info, redaction, text_extraction
from pdf_service.generated.redactr.pdf.v1 import pdf_service_pb2 as pb2
from pdf_service.generated.redactr.pdf.v1 import pdf_service_pb2_grpc as pb2_grpc


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
        try:
            result = redaction.apply_redactions(request.pdf_data, request.xfdf)
        except ValueError as e:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))
            return
        except Exception as e:
            context.abort(grpc.StatusCode.INTERNAL, f"Processing failed: {e}")
            return

        return pb2.ApplyRedactionsResponse(
            pdf_data=result["pdf_data"],
            redactions_applied=result["redactions_applied"],
            content_hash=result["content_hash"],
        )
