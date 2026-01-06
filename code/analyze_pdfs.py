"""
Analyze PDFs to determine text extraction quality.

Categorizes PDFs by text density to identify scanned vs text-based documents.
"""

import argparse
import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

import pymupdf


@dataclass
class PDFAnalysis:
    """Analysis result for a single PDF."""
    path: str
    page_count: int
    text_length: int
    chars_per_page: float
    category: str  # "text-rich", "sparse", "empty"
    error: str | None = None


def categorize(chars_per_page: float) -> str:
    """Categorize PDF by text density."""
    if chars_per_page >= 500:
        return "text-rich"
    elif chars_per_page >= 50:
        return "sparse"
    else:
        return "empty"


def analyze_pdf(pdf_path: Path) -> PDFAnalysis:
    """Analyze a single PDF for text content."""
    try:
        doc = pymupdf.open(pdf_path)
        page_count = len(doc)
        text = "".join(page.get_text() for page in doc)
        doc.close()

        text_length = len(text)
        chars_per_page = text_length / page_count if page_count > 0 else 0

        return PDFAnalysis(
            path=str(pdf_path),
            page_count=page_count,
            text_length=text_length,
            chars_per_page=chars_per_page,
            category=categorize(chars_per_page),
        )
    except Exception as e:
        return PDFAnalysis(
            path=str(pdf_path),
            page_count=0,
            text_length=0,
            chars_per_page=0,
            category="error",
            error=str(e),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze PDF text density")
    parser.add_argument("--pdf-dir", type=Path, default=Path("pdfs"))
    parser.add_argument("--sample", type=int, default=500, help="Number of PDFs to sample (0 = all)")
    parser.add_argument("--workers", type=int, default=8, help="Number of parallel workers")
    parser.add_argument("--show-empty", action="store_true", help="List empty/sparse PDFs")
    args = parser.parse_args()

    all_pdfs = list(args.pdf_dir.glob("*.pdf"))
    print(f"Found {len(all_pdfs):,} PDFs in {args.pdf_dir}")

    if args.sample > 0 and len(all_pdfs) > args.sample:
        pdfs = random.sample(all_pdfs, args.sample)
        print(f"Sampling {args.sample} PDFs")
    else:
        pdfs = all_pdfs

    results: list[PDFAnalysis] = []

    print(f"Analyzing with {args.workers} workers...")
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(analyze_pdf, p): p for p in pdfs}
        for i, future in enumerate(as_completed(futures), 1):
            results.append(future.result())
            if i % 100 == 0:
                print(f"  Processed {i}/{len(pdfs)}")

    # Summarize
    categories = Counter(r.category for r in results)
    total = len(results)

    print("\n" + "=" * 50)
    print("RESULTS")
    print("=" * 50)

    for cat in ["text-rich", "sparse", "empty", "error"]:
        count = categories.get(cat, 0)
        pct = (count / total * 100) if total > 0 else 0
        bar = "#" * int(pct / 2)
        print(f"{cat:12} {count:5} ({pct:5.1f}%) {bar}")

    print("\nCategory definitions:")
    print("  text-rich: >= 500 chars/page (standard text PDF)")
    print("  sparse:    50-500 chars/page (partial text, maybe mixed)")
    print("  empty:     < 50 chars/page (likely scanned/image-only)")

    # Stats for text-rich
    text_rich = [r for r in results if r.category == "text-rich"]
    if text_rich:
        avg_cpp = sum(r.chars_per_page for r in text_rich) / len(text_rich)
        print(f"\nText-rich avg: {avg_cpp:,.0f} chars/page")

    # Show problematic PDFs
    if args.show_empty:
        empty_sparse = [r for r in results if r.category in ("empty", "sparse")]
        if empty_sparse:
            print("\n" + "-" * 50)
            print("Empty/Sparse PDFs (likely need OCR):")
            for r in sorted(empty_sparse, key=lambda x: x.chars_per_page)[:20]:
                print(f"  {Path(r.path).name}: {r.chars_per_page:.0f} chars/page ({r.page_count} pages)")


if __name__ == "__main__":
    main()
