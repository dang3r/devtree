#!/usr/bin/env python3
"""
Count pages for all PDFs in the pdfs folder.

Uses multiprocessing for speed and saves results to a JSON manifest.

Usage:
    uv run code/count_pdf_pages.py
    uv run code/count_pdf_pages.py --output data/pdf_pages.json
"""

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import fitz  # PyMuPDF
from tqdm import tqdm


def count_pages(pdf_path: Path) -> tuple[str, int | None, str | None]:
    """Count pages in a single PDF. Returns (filename, page_count, error)."""
    try:
        with fitz.open(pdf_path) as doc:
            return (pdf_path.stem, len(doc), None)
    except Exception as e:
        return (pdf_path.stem, None, str(e))


def count_all_pages(
    pdfs_dir: Path,
    output_path: Path,
    max_workers: int = 8,
    save_interval: int = 1000,
) -> dict:
    """Count pages for all PDFs in directory."""
    pdf_files = list(pdfs_dir.glob("*.pdf"))
    total = len(pdf_files)

    print(f"Found {total:,} PDFs in {pdfs_dir}")

    results = {
        "total_pdfs": total,
        "processed": 0,
        "success": 0,
        "errors": 0,
        "total_pages": 0,
        "pages": {},
        "errors_detail": {},
    }

    start_time = time.time()

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(count_pages, pdf): pdf for pdf in pdf_files}

        with tqdm(total=total, desc="Counting pages", unit="pdf") as pbar:
            for i, future in enumerate(as_completed(futures), 1):
                filename, page_count, error = future.result()

                if error:
                    results["errors"] += 1
                    results["errors_detail"][filename] = error
                else:
                    results["success"] += 1
                    results["pages"][filename] = page_count
                    results["total_pages"] += page_count

                results["processed"] = i
                pbar.update(1)

                # Save periodically
                if i % save_interval == 0:
                    with open(output_path, "w") as f:
                        json.dump(results, f)

    # Final save
    elapsed = time.time() - start_time
    results["elapsed_seconds"] = elapsed

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    return results


def print_summary(results: dict) -> None:
    """Print summary statistics."""
    print("\n" + "=" * 50)
    print("PDF PAGE COUNT SUMMARY")
    print("=" * 50)
    print(f"Total PDFs:     {results['total_pdfs']:,}")
    print(f"Successful:     {results['success']:,}")
    print(f"Errors:         {results['errors']:,}")
    print(f"Total pages:    {results['total_pages']:,}")

    if results['success'] > 0:
        avg_pages = results['total_pages'] / results['success']
        print(f"Avg pages/PDF:  {avg_pages:.1f}")

    # Page distribution
    pages = list(results['pages'].values())
    if pages:
        pages_sorted = sorted(pages)
        print(f"\nPage distribution:")
        print(f"  Min:    {pages_sorted[0]}")
        print(f"  Max:    {pages_sorted[-1]}")
        print(f"  Median: {pages_sorted[len(pages_sorted)//2]}")

        # Histogram buckets
        buckets = [0, 1, 5, 10, 20, 50, 100, 200, 500, 1000, float('inf')]
        print(f"\nDistribution:")
        for i in range(len(buckets) - 1):
            low, high = buckets[i], buckets[i + 1]
            count = sum(1 for p in pages if low <= p < high)
            if count > 0:
                label = f"{low}-{int(high)-1}" if high != float('inf') else f"{low}+"
                pct = count / len(pages) * 100
                print(f"  {label:>10} pages: {count:>6,} ({pct:>5.1f}%)")

    if results.get('elapsed_seconds'):
        print(f"\nElapsed: {results['elapsed_seconds']:.1f}s")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Count pages in all PDFs")
    parser.add_argument(
        "--pdfs-dir",
        type=Path,
        default=Path(__file__).parent.parent / "pdfs",
        help="Directory containing PDFs",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent.parent / "data" / "pdf_pages.json",
        help="Output JSON file",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Number of parallel workers",
    )

    args = parser.parse_args()

    if not args.pdfs_dir.exists():
        print(f"Error: PDFs directory not found: {args.pdfs_dir}")
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)

    results = count_all_pages(
        args.pdfs_dir,
        args.output,
        max_workers=args.workers,
    )

    print_summary(results)
    print(f"Results saved to: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
