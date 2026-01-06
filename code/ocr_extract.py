"""
OCR extraction for scanned PDFs using Tesseract.

Processes PDFs categorized as "empty" or "sparse" in the manifest,
extracts text via OCR, and updates the text files and manifest.
"""

import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image
from pydantic import BaseModel
from pytesseract import Output
from tqdm import tqdm


class PDFMetadata(BaseModel):
    """Metadata for a single PDF."""

    page_count: int
    text_length: int
    chars_per_page: float
    category: str
    ocr_confidence: float | None = None
    error: str | None = None


def pdf_to_images(pdf_path: Path, dpi: int = 300) -> list[Image.Image]:
    """Convert PDF pages to PIL images for OCR."""
    doc = pymupdf.open(pdf_path)
    images = []
    mat = pymupdf.Matrix(dpi / 72, dpi / 72)
    for page in doc:
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)
    doc.close()
    return images


def ocr_images(images: list[Image.Image]) -> tuple[str, float]:
    """OCR images and return (text, avg_confidence)."""
    all_text = []
    confidences = []

    for img in images:
        data = pytesseract.image_to_data(img, output_type=Output.DICT)
        page_text = []
        for i, conf in enumerate(data["conf"]):
            conf_val = int(conf) if str(conf).lstrip("-").isdigit() else -1
            if conf_val > 0:
                confidences.append(conf_val)
                if data["text"][i].strip():
                    page_text.append(data["text"][i])
        all_text.append(" ".join(page_text))

    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    return "\n\n".join(all_text), round(avg_conf, 1)


def process_pdf_ocr(
    k_number: str, pdf_dir: Path, text_dir: Path, dpi: int = 300
) -> tuple[str, PDFMetadata]:
    """Run OCR on a single PDF and save text. Returns (k_number, metadata)."""
    pdf_path = pdf_dir / f"{k_number}.pdf"

    try:
        images = pdf_to_images(pdf_path, dpi=dpi)
        text, confidence = ocr_images(images)
        page_count = len(images)
        text_length = len(text)
        chars_per_page = text_length / page_count if page_count > 0 else 0.0

        # Save text file
        text_path = text_dir / f"{k_number}.txt"
        text_path.write_text(text)

        metadata = PDFMetadata(
            page_count=page_count,
            text_length=text_length,
            chars_per_page=round(chars_per_page, 1),
            category="ocr",
            ocr_confidence=confidence,
        )
        return k_number, metadata

    except Exception as e:
        metadata = PDFMetadata(
            page_count=0,
            text_length=0,
            chars_per_page=0.0,
            category="ocr-error",
            error=str(e),
        )
        return k_number, metadata


def load_manifest(manifest_path: Path) -> dict:
    """Load manifest from disk."""
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    return json.loads(manifest_path.read_text())


def save_manifest(manifest_path: Path, manifest: dict) -> None:
    """Save manifest to disk."""
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(json.dumps(manifest, indent=2))


def get_pdfs_needing_ocr(manifest: dict) -> list[str]:
    """Get list of K-numbers that need OCR (empty or sparse, not already OCR'd)."""
    needs_ocr = []
    for k_number, meta in manifest.get("pdfs", {}).items():
        category = meta.get("category", "")
        if category in ("empty", "sparse"):
            needs_ocr.append(k_number)
    return needs_ocr


def update_summary(manifest: dict) -> None:
    """Recalculate summary counts from pdfs data."""
    summary = {}
    for meta in manifest.get("pdfs", {}).values():
        cat = meta.get("category", "unknown")
        summary[cat] = summary.get(cat, 0) + 1
    manifest["summary"] = summary


def main(
    pdf_dir: Path = Path("pdfs"),
    text_dir: Path = Path("text"),
    workers: int = 8,
    save_interval: int = 500,
    dpi: int = 300,
) -> None:
    """Run OCR on all empty/sparse PDFs."""
    manifest_path = text_dir / "manifest.json"
    manifest = load_manifest(manifest_path)

    # Find PDFs needing OCR
    to_process = get_pdfs_needing_ocr(manifest)
    total = len(to_process)
    print(f"PDFs needing OCR: {total:,}")

    if not to_process:
        print("No PDFs need OCR!")
        return

    processed = 0
    success = 0
    errors = 0
    total_confidence = 0.0

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(process_pdf_ocr, k, pdf_dir, text_dir, dpi): k
            for k in to_process
        }

        with tqdm(total=total, desc="OCR extraction") as pbar:
            for future in as_completed(futures):
                k_number, metadata = future.result()
                manifest["pdfs"][k_number] = metadata.model_dump()
                processed += 1

                if metadata.category == "ocr":
                    success += 1
                    if metadata.ocr_confidence:
                        total_confidence += metadata.ocr_confidence
                else:
                    errors += 1

                pbar.update(1)

                # Periodic save
                if processed % save_interval == 0:
                    update_summary(manifest)
                    save_manifest(manifest_path, manifest)

    # Final save
    update_summary(manifest)
    save_manifest(manifest_path, manifest)

    # Summary
    avg_confidence = total_confidence / success if success > 0 else 0
    print("\n" + "=" * 60)
    print("OCR EXTRACTION COMPLETE")
    print("=" * 60)
    print(f"\nProcessed: {processed:,}")
    print(f"Success: {success:,}")
    print(f"Errors: {errors:,}")
    print(f"Average confidence: {avg_confidence:.1f}%")
    print(f"\nManifest updated: {manifest_path}")


if __name__ == "__main__":
    main()
