"""
Predicate extractor for FDA 510(k) PDFs.

Extracts K-numbers from PDF text using regex.
"""

import re
from pathlib import Path

import pymupdf
from pydantic import BaseModel


K_NUMBER_PATTERN = re.compile(r"K\d{6}")


class ExtractionResult(BaseModel):
    """Result of predicate extraction from a single PDF."""

    k_number: str
    pdf_path: str
    all_k_numbers_found: list[str]
    predicate_candidates: list[str]
    text_length: int
    page_count: int
    error: str | None = None


def extract_text_from_pdf(pdf_path: Path) -> tuple[str, int]:
    """Extract all text from a PDF. Returns (text, page_count)."""
    doc = pymupdf.open(pdf_path)
    text_parts = []
    for page in doc:
        text_parts.append(page.get_text())
    doc.close()
    return "\n".join(text_parts), len(text_parts)


def get_cached_text(k_number: str, text_dir: Path = Path("text")) -> str | None:
    """Load cached text if available, return None otherwise."""
    cache_path = text_dir / f"{k_number}.txt"
    if cache_path.exists():
        return cache_path.read_text()
    return None


def extract_k_numbers(text: str) -> list[str]:
    """Find all unique K-numbers in text."""
    matches = K_NUMBER_PATTERN.findall(text)
    # Preserve order, remove duplicates
    seen = set()
    unique = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            unique.append(m)
    return unique


def extract_predicates(pdf_path: Path) -> ExtractionResult:
    """Extract predicate K-numbers from a 510(k) PDF.

    The device's own K-number is inferred from the filename and excluded.
    """
    k_number = pdf_path.stem  # e.g., "K152289" from "K152289.pdf"

    try:
        text, page_count = extract_text_from_pdf(pdf_path)
        all_k_numbers = extract_k_numbers(text)

        # Filter out the device's own K-number
        predicates = [k for k in all_k_numbers if k != k_number]

        return ExtractionResult(
            k_number=k_number,
            pdf_path=str(pdf_path),
            all_k_numbers_found=all_k_numbers,
            predicate_candidates=predicates,
            text_length=len(text),
            page_count=page_count,
        )
    except Exception as e:
        return ExtractionResult(
            k_number=k_number,
            pdf_path=str(pdf_path),
            all_k_numbers_found=[],
            predicate_candidates=[],
            text_length=0,
            page_count=0,
            error=str(e),
        )


def main() -> None:
    """Test extraction on a sample PDF."""
    pdf_dir = Path("pdfs")

    # Find a few K-number PDFs to test
    k_pdfs = sorted(pdf_dir.glob("K*.pdf"))

    k_pdfs = [k for k in k_pdfs if k.stem.startswith("K22")][:10]

    print(f"Testing extraction on {len(k_pdfs)} PDFs\n")

    for pdf_path in k_pdfs:
        result = extract_predicates(pdf_path)

        print(f"=== {result.k_number} ===")
        print(
            f"  Pages: {result.page_count}, Text length: {result.text_length:,} chars"
        )
        print(f"  All K-numbers found: {result.all_k_numbers_found}")
        print(f"  Predicate candidates: {result.predicate_candidates}")
        if result.error:
            print(f"  ERROR: {result.error}")
        print()


if __name__ == "__main__":
    main()
