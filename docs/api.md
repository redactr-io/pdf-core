# API Reference



## PdfService

| Method | Request | Response | Description |
| ------ | ------- | -------- | ----------- |
| GetDocumentInfo | [PdfInput](#redactr-pdf-v1-pdfinput) | [DocumentInfoResponse](#redactr-pdf-v1-documentinforesponse) | Returns page count, file size, metadata, and per-page analysis. |
| ExtractText | [ExtractTextRequest](#redactr-pdf-v1-extracttextrequest) | stream [PageTextResponse](#redactr-pdf-v1-pagetextresponse) | Streams extracted text page-by-page, with optional word positions and OCR. |
| GetSuggestionAnnotations | [GetSuggestionAnnotationsRequest](#redactr-pdf-v1-getsuggestionannotationsrequest) | [GetSuggestionAnnotationsResponse](#redactr-pdf-v1-getsuggestionannotationsresponse) | Searches for text strings and returns XFDF XML with highlight annotations for review. |
| ApplyRedactions | [ApplyRedactionsRequest](#redactr-pdf-v1-applyredactionsrequest) | [ApplyRedactionsResponse](#redactr-pdf-v1-applyredactionsresponse) | Applies XFDF highlight annotations as redactions, permanently removing matched content. |



## Messages


### ApplyRedactionsRequest

Request to apply redactions from XFDF annotations.

| Field | Type | Description |
| ----- | ---- | ----------- |
| pdf_data | bytes | The PDF file contents. |
| xfdf | string | XFDF XML with highlight annotations to convert to redactions. |



### ApplyRedactionsResponse

Result of applying redactions to a PDF.

| Field | Type | Description |
| ----- | ---- | ----------- |
| pdf_data | bytes | The redacted PDF file contents. |
| redactions_applied | int32 | Number of redaction annotations that were applied. |
| content_hash | bytes | SHA-256 hash of the output PDF bytes. |



### DocumentInfoResponse

Document-level analysis results.

| Field | Type | Description |
| ----- | ---- | ----------- |
| page_count | int32 | Total number of pages in the document. |
| file_size_bytes | int64 | Size of the input PDF in bytes. |
| is_encrypted | bool | Whether the PDF is password-protected. |
| has_text_content | bool | Whether any page contains extractable text. |
| has_annotations | bool | Whether any page contains annotations. |
| existing_annotation_count | int32 | Total number of annotations across all pages. |
| metadata | DocumentMetadata | Document-level metadata (title, author, etc.). |
| pages | repeated PageInfo | Per-page analysis results. |



### DocumentMetadata

PDF document metadata fields.

| Field | Type | Description |
| ----- | ---- | ----------- |
| title | string | Document title. |
| author | string | Document author. |
| producer | string | Software that produced the PDF. |
| creator | string | Software that created the original document. |



### ExtractTextRequest

Request to extract text from a PDF.

| Field | Type | Description |
| ----- | ---- | ----------- |
| pdf_data | bytes | The PDF file contents. |
| pages | repeated int32 | Zero-indexed page numbers to extract. Empty means all pages. |
| include_word_positions | bool | When true, includes per-line bounding box coordinates. |
| ocr | OcrOptions | Optional OCR settings for scanned pages. |



### GetSuggestionAnnotationsRequest

Request to generate XFDF suggestion annotations.

| Field | Type | Description |
| ----- | ---- | ----------- |
| pdf_data | bytes | The PDF file contents. |
| texts | repeated string | Text strings to search for across all pages. |



### GetSuggestionAnnotationsResponse

XFDF annotation suggestions for review before redaction.

| Field | Type | Description |
| ----- | ---- | ----------- |
| xfdf | string | XFDF XML containing highlight annotations for each match. |
| total_suggestions | int32 | Total number of highlight annotations generated. |
| results | repeated SuggestionResult | Per-text, per-page match counts (only pages with matches are included). |



### OcrOptions

OCR configuration for scanned page text extraction.

| Field | Type | Description |
| ----- | ---- | ----------- |
| enabled | bool | Whether to enable OCR processing. |
| language | string | Tesseract language code (default: "eng"). |
| force | bool | When true, forces OCR even on pages with existing text. |



### PageInfo

Per-page analysis results.

| Field | Type | Description |
| ----- | ---- | ----------- |
| page_number | int32 | Zero-indexed page number. |
| has_text | bool | Whether the page contains extractable text. |
| has_images | bool | Whether the page contains embedded images. |
| likely_scanned | bool | True if the page has images but no text (likely a scan). |
| width | float | Page width in points. |
| height | float | Page height in points. |



### PageTextResponse

Extracted text for a single page.

| Field | Type | Description |
| ----- | ---- | ----------- |
| page_number | int32 | Zero-indexed page number. |
| text | string | Full extracted text content of the page. |
| blocks | repeated TextBlock | Per-line text blocks with bounding boxes (only when include_word_positions is true). |



### PdfInput

Raw PDF bytes input.

| Field | Type | Description |
| ----- | ---- | ----------- |
| pdf_data | bytes | The PDF file contents. |



### SuggestionResult

Match results for a single text string on a single page.

| Field | Type | Description |
| ----- | ---- | ----------- |
| text | string | The text string that was searched for. |
| page | int32 | Zero-indexed page number. |
| occurrences_found | int32 | Number of times the text was found on this page. |



### TextBlock

A line of text with its bounding box coordinates.

| Field | Type | Description |
| ----- | ---- | ----------- |
| text | string | The text content of this line. |
| x0 | float | Left edge of the bounding box in points. |
| y0 | float | Top edge of the bounding box in points. |
| x1 | float | Right edge of the bounding box in points. |
| y1 | float | Bottom edge of the bounding box in points. |
| block_number | int32 | Index of the parent text block on the page. |
| line_number | int32 | Line index within the parent text block. |



