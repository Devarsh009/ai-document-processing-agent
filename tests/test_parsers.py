import os
import tempfile
import pytest
from app.parsers.document_parser import (
    parse_document,
    validate_file_bytes,
    DocumentExceedsSizeLimitError,
    UnsupportedFileTypeError,
)


def test_validate_file_bytes_valid_txt():
    ext, mime = validate_file_bytes(b"Hello world", "note.txt")
    assert ext == ".txt"
    assert mime == "text/plain"


def test_validate_file_bytes_valid_pdf():
    ext, mime = validate_file_bytes(b"%PDF-1.4 sample pdf content", "doc.pdf")
    assert ext == ".pdf"
    assert mime == "application/pdf"


def test_validate_file_bytes_invalid_magic_pdf():
    with pytest.raises(UnsupportedFileTypeError):
        validate_file_bytes(b"NOT_PDF", "doc.pdf")


def test_validate_file_bytes_size_exceeded():
    large_bytes = b"x" * (11 * 1024 * 1024)
    with pytest.raises(DocumentExceedsSizeLimitError):
        validate_file_bytes(large_bytes, "large.txt")


def test_parse_txt_file():
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".txt", encoding="utf-8") as tf:
        tf.write("Sample invoice line items and totals.")
        temp_path = tf.name

    try:
        parsed = parse_document(temp_path)
        assert parsed.format == "txt"
        assert parsed.page_count == 1
        assert "Sample invoice" in parsed.text
        assert parsed.is_scanned_or_empty is False
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
