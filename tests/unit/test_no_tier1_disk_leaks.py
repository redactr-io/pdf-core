"""Tier 1 ephemeral storage cleanup.

PRIVACY-GUARANTEE.md §1 (sibling Redactr platform repo) promises that on job
completion — success, failure, or cancellation — all Tier 1 storage is deleted
within 60 seconds. pdf-core is the service where rasterization and OCR happen,
which is the realistic place for transient disk writes to appear (Tesseract is
known to use a scratch file for its image input on some platforms).

This module routes any tempfile writes into a pytest-managed `tmp_path` by
setting both Python's `tempfile.tempdir` and the `TMPDIR` env var (which the
Tesseract C library and PyMuPDF respect), runs each core function, and asserts
the scratch directory is empty after the call returns or raises.
"""

import os
import tempfile
from pathlib import Path

import fitz
import pytest

from pdf_service.core import (
    annotation,
    document_info,
    redaction,
    risky_annotations,
    text_extraction,
    verification,
)
from pdf_service.core.ocr import ocr_page


def _isolate_tempdir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Force every layer that might write a scratch file into `tmp_path`."""
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    return tmp_path


def _files_in(scratch: Path) -> list[Path]:
    return [p for p in scratch.rglob("*") if p.is_file()]


class TestNoTier1DiskLeaks:
    def test_tmpdir_isolation_is_in_effect(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Sanity check: if TMPDIR isolation breaks, all other tests in this
        module silently pass without verifying anything."""
        scratch = _isolate_tempdir(monkeypatch, tmp_path)
        with tempfile.NamedTemporaryFile(delete=False) as f:
            sentinel = Path(f.name)
        try:
            assert sentinel.parent.resolve() == scratch.resolve()
            assert os.environ["TMPDIR"] == str(scratch)
        finally:
            sentinel.unlink(missing_ok=True)

    def test_ocr_does_not_leak_temp_files(
        self,
        scanned_pdf: bytes,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        scratch = _isolate_tempdir(monkeypatch, tmp_path)
        doc = fitz.open(stream=scanned_pdf, filetype="pdf")
        try:
            ocr_page(doc[0])
        except RuntimeError as e:
            if "Tesseract" in str(e):
                pytest.skip("Tesseract not installed")
            raise
        finally:
            doc.close()

        leaked = _files_in(scratch)
        assert not leaked, f"OCR left files in TMPDIR: {leaked}"

    def test_extract_text_with_ocr_does_not_leak(
        self,
        scanned_pdf: bytes,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        scratch = _isolate_tempdir(monkeypatch, tmp_path)
        try:
            list(
                text_extraction.extract_text(
                    scanned_pdf,
                    None,
                    False,
                    {"enabled": True, "force": True},
                )
            )
        except RuntimeError as e:
            if "Tesseract" in str(e):
                pytest.skip("Tesseract not installed")
            raise

        leaked = _files_in(scratch)
        assert not leaked, f"extract_text with OCR left files in TMPDIR: {leaked}"

    def test_extract_text_no_ocr_does_not_leak(
        self,
        text_pdf: bytes,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        scratch = _isolate_tempdir(monkeypatch, tmp_path)
        list(text_extraction.extract_text(text_pdf, None, True, None))
        assert not _files_in(scratch)

    def test_get_document_info_does_not_leak(
        self,
        text_pdf: bytes,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        scratch = _isolate_tempdir(monkeypatch, tmp_path)
        document_info.get_document_info(text_pdf)
        assert not _files_in(scratch)

    def test_get_suggestion_annotations_does_not_leak(
        self,
        text_pdf: bytes,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        scratch = _isolate_tempdir(monkeypatch, tmp_path)
        annotation.get_suggestion_annotations(text_pdf, [{"text": "John Smith"}])
        assert not _files_in(scratch)

    def test_apply_redactions_does_not_leak(
        self,
        text_pdf: bytes,
        suggestion_xfdf: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        scratch = _isolate_tempdir(monkeypatch, tmp_path)
        redaction.apply_redactions(text_pdf, suggestion_xfdf)
        assert not _files_in(scratch)

    def test_verify_redactions_does_not_leak(
        self,
        text_pdf: bytes,
        suggestion_xfdf: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        scratch = _isolate_tempdir(monkeypatch, tmp_path)
        applied = redaction.apply_redactions(text_pdf, suggestion_xfdf)
        # Reset the scratch dir state in case apply_redactions wrote anything;
        # this test isolates verify_redactions itself.
        for p in _files_in(scratch):
            p.unlink()
        verification.verify_redactions(applied["pdf_data"], applied["redaction_log"])
        assert not _files_in(scratch)

    def test_detect_risky_annotations_does_not_leak(
        self,
        pdf_with_filled_square_over_text: bytes,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        scratch = _isolate_tempdir(monkeypatch, tmp_path)
        risky_annotations.detect_risky_annotations(pdf_with_filled_square_over_text)
        assert not _files_in(scratch)

    def test_failure_path_does_not_leak(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A failing request must still leave the scratch dir clean."""
        scratch = _isolate_tempdir(monkeypatch, tmp_path)
        with pytest.raises(ValueError):
            list(
                text_extraction.extract_text(
                    b"not-a-pdf",
                    None,
                    False,
                    {"enabled": True, "force": True},
                )
            )
        assert not _files_in(scratch)
