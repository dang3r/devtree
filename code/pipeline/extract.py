"""
Text and predicate extraction from PDFs.

Combines text extraction (PyMuPDF) with OCR fallback (Ollama) and predicate
extraction into a single pipeline step. Also flags suspicious devices for review.
"""

import re
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Literal

import pymupdf
from pydantic import BaseModel
from tqdm import tqdm

# Add parent directory to path for ocr_pdf import
sys.path.insert(0, str(Path(__file__).parent.parent))
from ocr_pdf import ocr_pdf as ollama_ocr

# Thresholds for OCR fallback
OCR_FALLBACK_THRESHOLD = 50  # chars/page triggers OCR
SPARSE_TEXT_THRESHOLD = 100  # chars/page considered sparse

K_NUMBER_PATTERN = re.compile(r"K\d{6}")
MALFORMED_PATTERN = re.compile(r"K\s*\d[\s\d]{5,7}")  # K with spaces in digits


class TextMetadata(BaseModel):
    """Metadata from text extraction."""

    page_count: int
    text_length: int
    chars_per_page: float
    category: Literal["text-rich", "sparse", "empty", "error"]


class PredicateResult(BaseModel):
    """Predicate extraction result."""

    predicates: list[str]
    all_k_numbers_found: list[str]
    malformed_matches: list[str]


class SuspiciousFlag(BaseModel):
    """Flag for devices needing LLM review."""

    reason: Literal[
        "no_predicates", "excessive_predicates", "sparse_text", "malformed_knumber"
    ]
    details: str


class ExtractionResult(BaseModel):
    """Complete extraction result for a single device."""

    k_number: str
    text_metadata: TextMetadata
    predicates: PredicateResult
    flags: list[SuspiciousFlag]
    error: str | None = None
    extraction_method: Literal["pymupdf", "ocr", "none"] = "none"
    ocr_attempted: bool = False
    ocr_error: str | None = None


class ExtractionSummary(BaseModel):
    """Summary of all extractions."""

    total: int
    success: int
    errors: int
    with_predicates: int
    flagged: int
    ocr_used: int = 0
    ocr_failed: int = 0


def extract_text_from_pdf(pdf_path: Path) -> tuple[str, int]:
    """Extract text from PDF using PyMuPDF."""
    doc = pymupdf.open(pdf_path)
    text_parts = []
    for page in doc:
        text_parts.append(page.get_text())
    page_count = len(text_parts)
    doc.close()
    return "\n".join(text_parts), page_count


def categorize_text_density(
    chars_per_page: float,
) -> Literal["text-rich", "sparse", "empty"]:
    """Categorize PDF by text density."""
    if chars_per_page >= 500:
        return "text-rich"
    elif chars_per_page >= 50:
        return "sparse"
    else:
        return "empty"


def extract_k_numbers(text: str) -> list[str]:
    """Find all unique K-numbers, preserving order."""
    matches = K_NUMBER_PATTERN.findall(text)
    return list(set(matches))


def find_malformed_k_numbers(text: str) -> list[str]:
    """Find K-numbers with spaces or typos."""
    matches = MALFORMED_PATTERN.findall(text)
    # Filter out valid K-numbers that might match
    malformed = []
    for m in matches:
        normalized = re.sub(r"\s", "", m)
        if not K_NUMBER_PATTERN.fullmatch(normalized):
            malformed.append(m.strip())
    return malformed


def check_suspicious(
    k_number: str,
    predicates: list[str],
    text_metadata: TextMetadata,
    malformed: list[str],
) -> list[SuspiciousFlag]:
    """Check if device should be flagged for LLM review."""
    flags = []

    # No predicates but text-rich (suspicious)
    if not predicates and text_metadata.chars_per_page > 100:
        flags.append(
            SuspiciousFlag(
                reason="no_predicates",
                details=f"No predicates found despite {text_metadata.chars_per_page:.0f} chars/page",
            )
        )

    # Excessive predicates (likely noise)
    if len(predicates) >= 10:
        flags.append(
            SuspiciousFlag(
                reason="excessive_predicates",
                details=f"Found {len(predicates)} predicates - may include non-predicate references",
            )
        )

    # Sparse text (OCR might have failed)
    if text_metadata.category == "empty":
        flags.append(
            SuspiciousFlag(
                reason="sparse_text",
                details=f"Only {text_metadata.chars_per_page:.0f} chars/page - may be image-based",
            )
        )

    # Malformed K-numbers found
    if malformed:
        flags.append(
            SuspiciousFlag(
                reason="malformed_knumber",
                details=f"Found malformed patterns: {malformed[:3]}",
            )
        )

    return flags


def should_use_ocr(chars_per_page: float) -> bool:
    """Determine if OCR fallback should be used."""
    return chars_per_page < OCR_FALLBACK_THRESHOLD


def extract_with_ocr(
    pdf_path: Path,
    model: str = "gemma3",
    ollama_url: str = "http://localhost:11434",
) -> tuple[str, str | None]:
    """
    Extract text using Ollama OCR.

    Returns:
        (extracted_text, error_message or None)
    """
    try:
        text = ollama_ocr(pdf_path, output_path=None, model=model)
        return text, None
    except Exception as e:
        return "", str(e)


def process_single_pdf(
    pdf_path: Path,
    text_dir: Path,
    use_ocr_fallback: bool = True,
    ocr_model: str = "gemma3",
) -> ExtractionResult:
    """Process a single PDF with two-path extraction (PyMuPDF + OCR fallback)."""
    k_number = pdf_path.stem
    text_path = text_dir / f"{k_number}.txt"
    extraction_method: Literal["pymupdf", "ocr", "none"] = "none"
    ocr_attempted = False
    ocr_error: str | None = None

    try:
        # Path 1: PyMuPDF text extraction
        text, page_count = extract_text_from_pdf(pdf_path)
        text_length = len(text)
        chars_per_page = text_length / page_count if page_count > 0 else 0.0
        extraction_method = "pymupdf"

        # Extract predicates from original text (path 1)
        all_k_numbers = extract_k_numbers(text)
        predicates = [k for k in all_k_numbers if k != k_number]

        # Path 2: OCR fallback if no predicates found
        if use_ocr_fallback and not predicates:
            ocr_attempted = True
            ocr_text, ocr_error = extract_with_ocr(pdf_path, model=ocr_model)

            if not ocr_error and len(ocr_text) > text_length:
                # OCR produced more text, use it
                text = ocr_text
                text_length = len(text)
                chars_per_page = text_length / page_count if page_count > 0 else 0.0
                extraction_method = "ocr"
                # Re-extract predicates/malformed
                all_k_numbers = extract_k_numbers(text)
                predicates = [k for k in all_k_numbers if k != k_number]
                malformed = find_malformed_k_numbers(text)

        # Save text file
        text_path.write_text(text)

        category = categorize_text_density(chars_per_page)
        text_metadata = TextMetadata(
            page_count=page_count,
            text_length=text_length,
            chars_per_page=round(chars_per_page, 1),
            category=category,
        )

        predicate_result = PredicateResult(
            predicates=predicates,
            all_k_numbers_found=all_k_numbers,
            malformed_matches=malformed,
        )

        # Check for suspicious patterns
        flags = check_suspicious(k_number, predicates, text_metadata, malformed)

        return ExtractionResult(
            k_number=k_number,
            text_metadata=text_metadata,
            predicates=predicate_result,
            flags=flags,
            extraction_method=extraction_method,
            ocr_attempted=ocr_attempted,
            ocr_error=ocr_error,
        )

    except Exception as e:
        return ExtractionResult(
            k_number=k_number,
            text_metadata=TextMetadata(
                page_count=0,
                text_length=0,
                chars_per_page=0.0,
                category="error",
            ),
            predicates=PredicateResult(
                predicates=[],
                all_k_numbers_found=[],
                malformed_matches=[],
            ),
            flags=[],
            error=str(e),
            extraction_method=extraction_method,
            ocr_attempted=ocr_attempted,
            ocr_error=ocr_error,
        )


def extract_all(
    k_numbers: list[str],
    pdf_dir: Path,
    text_dir: Path,
    workers: int = 4,
    use_ocr_fallback: bool = True,
    ocr_model: str = "gemma3",
) -> tuple[list[ExtractionResult], ExtractionSummary]:
    """Extract text and predicates from all PDFs with progress tracking."""
    text_dir.mkdir(parents=True, exist_ok=True)

    # Find PDFs for specified K-numbers
    pdf_paths = []
    for k_num in k_numbers:
        pdf_path = pdf_dir / f"{k_num}.pdf"
        if pdf_path.exists():
            pdf_paths.append(pdf_path)

    print(
        f"Extracting from {len(pdf_paths)} PDFs (OCR fallback: {use_ocr_fallback})..."
    )

    results: list[ExtractionResult] = []

    # Use ProcessPoolExecutor but note: OCR uses network calls to Ollama
    # so we may want to limit parallelism when OCR is enabled
    effective_workers = min(workers, 2) if use_ocr_fallback else workers

    with ProcessPoolExecutor(max_workers=effective_workers) as executor:
        futures = {
            executor.submit(
                process_single_pdf, pdf, text_dir, use_ocr_fallback, ocr_model
            ): pdf
            for pdf in pdf_paths
        }

        with tqdm(total=len(futures), desc="Extracting", unit="pdf") as pbar:
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                pbar.update(1)
                pbar.set_postfix(
                    {
                        "last": result.k_number,
                        "method": result.extraction_method,
                    }
                )

    # Summarize
    success = sum(1 for r in results if not r.error)
    errors = sum(1 for r in results if r.error)
    with_preds = sum(1 for r in results if r.predicates.predicates)
    flagged = sum(1 for r in results if r.flags)
    ocr_used = sum(1 for r in results if r.extraction_method == "ocr")
    ocr_failed = sum(1 for r in results if r.ocr_attempted and r.ocr_error)

    print(f"  Success: {success}, Errors: {errors}")
    print(f"  With predicates: {with_preds}, Flagged: {flagged}")
    print(f"  OCR used: {ocr_used}, OCR failed: {ocr_failed}")

    summary = ExtractionSummary(
        total=len(k_numbers),
        success=success,
        errors=errors,
        with_predicates=with_preds,
        flagged=flagged,
        ocr_used=ocr_used,
        ocr_failed=ocr_failed,
    )

    return results, summary


def update_predicates_json(
    results: list[ExtractionResult],
    predicates_path: Path,
) -> None:
    """Update predicates.json with new extraction results."""
    # Load existing
    if predicates_path.exists():
        with open(predicates_path) as f:
            data = json.load(f)
    else:
        data = {"devices": {}}

    # Update with new results
    for result in results:
        if not result.error:
            data["devices"][result.k_number] = {
                "predicates": result.predicates.predicates,
                "predicate_count": len(result.predicates.predicates),
                "text_length": result.text_metadata.text_length,
            }

    # Update stats
    devices = data["devices"]
    data["total_devices"] = len(devices)
    data["with_predicates"] = sum(1 for d in devices.values() if d["predicates"])
    data["without_predicates"] = data["total_devices"] - data["with_predicates"]
    data["total_predicate_references"] = sum(
        d["predicate_count"] for d in devices.values()
    )

    with open(predicates_path, "w") as f:
        json.dump(data, f, indent=2)


def update_suspicious_json(
    results: list[ExtractionResult],
    suspicious_path: Path,
) -> None:
    """Update suspicious.json with flagged devices."""
    # Load existing
    if suspicious_path.exists():
        with open(suspicious_path) as f:
            data = json.load(f)
    else:
        data = {"devices": []}

    # Get existing K-numbers to avoid duplicates
    existing_k_nums = {d["k_number"] for d in data["devices"]}

    # Add new flagged devices
    for result in results:
        if result.flags and result.k_number not in existing_k_nums:
            data["devices"].append(
                {
                    "k_number": result.k_number,
                    "flags": [f.model_dump() for f in result.flags],
                    "text_snippet": "",  # Could add first 500 chars if needed
                }
            )

    with open(suspicious_path, "w") as f:
        json.dump(data, f, indent=2)
