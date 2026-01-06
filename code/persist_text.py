"""
Extract and persist text from all PDFs to text/ folder.

Features:
- Resumable: skips PDFs where text file already exists
- Periodic saves: writes manifest every 1000 documents
- Multiprocessing: uses ProcessPoolExecutor for CPU-bound extraction
- Progress bar: tqdm for ETA tracking
"""

import json
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path


from pydantic import BaseModel
from tqdm import tqdm

from extractor import extract_text_from_pdf


class PDFMetadata(BaseModel):
    """Metadata for a single PDF."""

    page_count: int
    text_length: int
    chars_per_page: float
    category: str  # "text-rich", "sparse", "empty"
    error: str | None = None


class Manifest(BaseModel):
    """Manifest tracking all processed PDFs."""

    generated_at: str
    total_pdfs: int
    processed: int
    summary: dict[str, int]
    pdfs: dict[str, PDFMetadata]


def categorize(chars_per_page: float) -> str:
    """Categorize PDF by text density."""
    if chars_per_page >= 500:
        return "text-rich"
    elif chars_per_page >= 50:
        return "sparse"
    else:
        return "empty"


def process_pdf(pdf_path: Path, text_dir: Path) -> tuple[str, PDFMetadata, str]:
    """Extract text from PDF and save to text file. Returns (k_number, metadata, text)."""
    k_number = pdf_path.stem

    try:
        text, page_count = extract_text_from_pdf(pdf_path)
        text_length = len(text)
        chars_per_page = text_length / page_count if page_count > 0 else 0.0
        category = categorize(chars_per_page)

        # Save text file
        text_path = text_dir / f"{k_number}.txt"
        text_path.write_text(text)

        metadata = PDFMetadata(
            page_count=page_count,
            text_length=text_length,
            chars_per_page=round(chars_per_page, 1),
            category=category,
        )
        return k_number, metadata, text

    except Exception as e:
        metadata = PDFMetadata(
            page_count=0,
            text_length=0,
            chars_per_page=0.0,
            category="error",
            error=str(e),
        )
        return k_number, metadata, ""


def load_existing_manifest(manifest_path: Path) -> dict[str, PDFMetadata]:
    """Load existing manifest if available."""
    if not manifest_path.exists():
        return {}
    try:
        data = json.loads(manifest_path.read_text())
        return {k: PDFMetadata(**v) for k, v in data.get("pdfs", {}).items()}
    except Exception:
        return {}


def save_manifest(
    manifest_path: Path, pdfs: dict[str, PDFMetadata], total_pdfs: int
) -> None:
    """Save manifest to disk."""
    summary = {"text-rich": 0, "sparse": 0, "empty": 0, "error": 0}
    for meta in pdfs.values():
        if meta.category in summary:
            summary[meta.category] += 1

    manifest = Manifest(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_pdfs=total_pdfs,
        processed=len(pdfs),
        summary=summary,
        pdfs=pdfs,
    )

    manifest_path.write_text(manifest.model_dump_json(indent=2))


def main(
    pdf_dir: Path = Path("pdfs"),
    text_dir: Path = Path("text"),
    workers: int = 8,
    save_interval: int = 1000,
) -> None:
    """Extract text from all PDFs and save to text/ folder."""
    # Setup
    text_dir.mkdir(exist_ok=True)
    manifest_path = text_dir / "manifest.json"

    # Find all PDFs
    all_pdfs = sorted(pdf_dir.glob("*.pdf"))
    total_pdfs = len(all_pdfs)
    print(f"Found {total_pdfs:,} PDFs")

    # Load existing progress
    existing = load_existing_manifest(manifest_path)
    print(f"Already processed: {len(existing):,}")

    # Filter to unprocessed PDFs
    pdfs_to_process = [p for p in all_pdfs if p.stem not in existing]
    print(f"Remaining: {len(pdfs_to_process):,}")

    if not pdfs_to_process:
        print("All PDFs already processed!")
        return

    # Start with existing data
    all_metadata = dict(existing)
    processed_since_save = 0

    # Process with multiprocessing
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(process_pdf, pdf, text_dir): pdf for pdf in pdfs_to_process
        }

        with tqdm(total=len(pdfs_to_process), desc="Extracting text") as pbar:
            for future in as_completed(futures):
                k_number, metadata, _ = future.result()
                all_metadata[k_number] = metadata
                processed_since_save += 1
                pbar.update(1)

                # Periodic save
                if processed_since_save >= save_interval:
                    save_manifest(manifest_path, all_metadata, total_pdfs)
                    processed_since_save = 0

    # Final save
    save_manifest(manifest_path, all_metadata, total_pdfs)

    # Print summary
    print("\n" + "=" * 60)
    print("EXTRACTION COMPLETE")
    print("=" * 60)

    summary = {"text-rich": 0, "sparse": 0, "empty": 0, "error": 0}
    for meta in all_metadata.values():
        if meta.category in summary:
            summary[meta.category] += 1

    print(f"\nTotal PDFs: {total_pdfs:,}")
    print(f"Text-rich (>= 500 chars/pg): {summary['text-rich']:,}")
    print(f"Sparse (50-500 chars/pg): {summary['sparse']:,}")
    print(f"Empty/scanned (< 50 chars/pg): {summary['empty']:,}")
    print(f"Errors: {summary['error']:,}")
    print(f"\nPDFs needing OCR: {summary['empty']:,}")
    print(f"Manifest saved to: {manifest_path}")


if __name__ == "__main__":
    main()
