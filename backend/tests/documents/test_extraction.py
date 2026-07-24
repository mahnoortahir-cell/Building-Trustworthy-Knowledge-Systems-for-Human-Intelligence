from pathlib import Path

import pytest
from pypdf import PdfWriter
from reportlab.pdfgen import canvas

from app.documents.extraction import (
    DocumentExtractionError,
    extract_pdf_text,
)


def create_blank_pdf(file_path: Path) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)

    with file_path.open("wb") as output_file:
        writer.write(output_file)

def create_text_pdf(
    file_path: Path,
    text: str,
) -> None:
    pdf = canvas.Canvas(str(file_path))
    pdf.drawString(72, 720, text)
    pdf.save()

def test_extract_pdf_rejects_missing_file(
    tmp_path: Path,
) -> None:
    missing_file = tmp_path / "missing.pdf"

    with pytest.raises(
        DocumentExtractionError,
        match="The stored document file could not be found.",
    ):
        extract_pdf_text(str(missing_file))


def test_extract_pdf_rejects_directory_path(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        DocumentExtractionError,
        match="The document storage path is not a file.",
    ):
        extract_pdf_text(str(tmp_path))


def test_extract_pdf_rejects_invalid_pdf(
    tmp_path: Path,
) -> None:
    invalid_pdf = tmp_path / "invalid.pdf"
    invalid_pdf.write_bytes(b"This is not a valid PDF.")

    with pytest.raises(
        DocumentExtractionError,
        match="Text could not be extracted from the PDF.",
    ):
        extract_pdf_text(str(invalid_pdf))


def test_extract_pdf_rejects_pdf_without_text(
    tmp_path: Path,
) -> None:
    blank_pdf = tmp_path / "blank.pdf"
    create_blank_pdf(blank_pdf)

    with pytest.raises(
        DocumentExtractionError,
        match="No extractable text was found in the PDF.",
    ):
        extract_pdf_text(str(blank_pdf))

def test_extract_pdf_text_successfully(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "document.pdf"
    expected_text = "NoorOS trustworthy knowledge system"

    create_text_pdf(
        file_path=pdf_path,
        text=expected_text,
    )

    result = extract_pdf_text(str(pdf_path))

    assert expected_text in result.text
    assert result.page_count == 1
    assert result.character_count == len(result.text)
    assert result.character_count > 0        