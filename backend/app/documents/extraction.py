from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class DocumentExtractionError(Exception):
    """Raised when text cannot be extracted from a document."""


@dataclass(frozen=True)
class ExtractionResult:
    text: str
    page_count: int
    character_count: int


def extract_pdf_text(storage_path: str) -> ExtractionResult:
    """Extract readable text from every page of a stored PDF."""

    file_path = Path(storage_path)

    if not file_path.exists():
        raise DocumentExtractionError(
            "The stored document file could not be found."
        )

    if not file_path.is_file():
        raise DocumentExtractionError(
            "The document storage path is not a file."
        )

    try:
        reader = PdfReader(str(file_path))

        if reader.is_encrypted:
            raise DocumentExtractionError(
                "Encrypted PDF documents are not currently supported."
            )

        extracted_pages: list[str] = []

        for page in reader.pages:
            page_text = page.extract_text() or ""
            cleaned_page_text = page_text.strip()

            if cleaned_page_text:
                extracted_pages.append(cleaned_page_text)

    except DocumentExtractionError:
        raise

    except (PdfReadError, OSError, ValueError) as exc:
        raise DocumentExtractionError(
            "Text could not be extracted from the PDF."
        ) from exc

    combined_text = "\n\n".join(extracted_pages).strip()

    if not combined_text:
        raise DocumentExtractionError(
            "No extractable text was found in the PDF."
        )

    return ExtractionResult(
        text=combined_text,
        page_count=len(reader.pages),
        character_count=len(combined_text),
    )