"""
Benchmark different predicate extraction approaches.

Compares:
1. Regex-only (baseline)
2. Text → Ollama LLM (gemini-3-flash-preview)
3. PDF → Images → Vision OCR (deepseek-ocr)
"""

import argparse
import asyncio
import base64
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import pymupdf

from extractor import extract_k_numbers, extract_text_from_pdf


OLLAMA_URL = "http://localhost:11434"

TEXT_MODEL = "gemma3"  # Local model for text extraction
VISION_MODEL = "deepseek-ocr"

EXTRACTION_PROMPT = """Extract all predicate device K-numbers from this FDA 510(k) document.

A predicate device is a legally marketed device that the new device is being compared to for substantial equivalence.
K-numbers follow the format K followed by 6 digits (e.g., K123456).

Return ONLY a JSON array of K-numbers found as predicates. Do not include the device's own K-number.
Example response: ["K123456", "K234567"]

If no predicates are found, return: []

Document text:
{text}
"""

VISION_PROMPT = """This is an FDA 510(k) document page. Extract all K-numbers you can see.
K-numbers follow the format K followed by 6 digits (e.g., K123456).

Return ONLY a JSON array of K-numbers found.
Example: ["K123456", "K234567"]
If none found: []
"""


@dataclass
class BenchmarkResult:
    """Result from a single extraction benchmark."""

    pdf_path: str
    k_number: str
    method: str
    predicates: list[str]
    duration_ms: float
    error: str | None = None
    raw_response: str = ""


@dataclass
class BenchmarkSummary:
    """Summary of benchmark results for a method."""

    method: str
    total_pdfs: int
    successful: int
    failed: int
    avg_duration_ms: float
    total_predicates_found: int
    results: list[BenchmarkResult] = field(default_factory=list)


async def call_ollama_text(
    client: httpx.AsyncClient, prompt: str, model: str = TEXT_MODEL
) -> str:
    """Call Ollama with a text prompt."""
    response = await client.post(
        f"{OLLAMA_URL}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=120.0,
    )
    response.raise_for_status()
    return response.json()["response"]


async def call_ollama_vision(
    client: httpx.AsyncClient,
    images_b64: list[str],
    prompt: str,
    model: str = VISION_MODEL,
) -> str:
    """Call Ollama with images for vision model."""
    messages = [
        {
            "role": "user",
            "content": prompt,
            "images": images_b64,
        }
    ]
    response = await client.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": model,
            "messages": messages,
            "stream": False,
        },
        timeout=180.0,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]


def pdf_to_images_b64(pdf_path: Path, max_pages: int = 3, dpi: int = 200) -> list[str]:
    """Convert PDF pages to base64-encoded PNG images."""
    doc = pymupdf.open(pdf_path)
    images = []

    for i, page in enumerate(doc):
        if i >= max_pages:
            break
        # Render page to pixmap at higher DPI for better OCR
        mat = pymupdf.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        images.append(base64.b64encode(img_bytes).decode("utf-8"))

    doc.close()
    return images


def parse_k_numbers_from_response(response: str) -> list[str]:
    """Parse K-numbers from LLM response, handling various formats."""
    # Try to find JSON array in response
    import re

    # Look for JSON array pattern
    match = re.search(r"\[.*?\]", response, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group())
            if isinstance(parsed, list):
                return [k for k in parsed if re.match(r"^K\d{6}$", str(k))]
        except json.JSONDecodeError:
            pass

    # Fallback: find all K-numbers in response
    return re.findall(r"K\d{6}", response)


async def benchmark_regex(
    client: httpx.AsyncClient, pdf_path: Path, executor: ThreadPoolExecutor
) -> BenchmarkResult:
    """Benchmark regex-only extraction."""
    k_number = pdf_path.stem
    start = time.perf_counter()

    try:
        # Run CPU-bound PDF extraction in thread pool
        loop = asyncio.get_event_loop()
        text, _ = await loop.run_in_executor(executor, extract_text_from_pdf, pdf_path)
        all_k = extract_k_numbers(text)
        predicates = [k for k in all_k if k != k_number]
        duration = (time.perf_counter() - start) * 1000

        return BenchmarkResult(
            pdf_path=str(pdf_path),
            k_number=k_number,
            method="regex",
            predicates=predicates,
            duration_ms=duration,
        )
    except Exception as e:
        return BenchmarkResult(
            pdf_path=str(pdf_path),
            k_number=k_number,
            method="regex",
            predicates=[],
            duration_ms=(time.perf_counter() - start) * 1000,
            error=str(e),
        )


async def benchmark_llm_text(
    client: httpx.AsyncClient, pdf_path: Path, executor: ThreadPoolExecutor
) -> BenchmarkResult:
    """Benchmark text → LLM extraction."""
    k_number = pdf_path.stem
    start = time.perf_counter()

    try:
        loop = asyncio.get_event_loop()
        text, page_count = await loop.run_in_executor(
            executor, extract_text_from_pdf, pdf_path
        )

        # Skip LLM if insufficient text (likely scanned PDF - avoids hallucinations)
        chars_per_page = len(text) / page_count if page_count > 0 else 0
        if chars_per_page < 100:
            return BenchmarkResult(
                pdf_path=str(pdf_path),
                k_number=k_number,
                method="llm_text",
                predicates=[],
                duration_ms=(time.perf_counter() - start) * 1000,
                raw_response="[SKIPPED: insufficient text - likely scanned PDF]",
            )

        # Truncate text if too long (keep first ~8k chars)
        if len(text) > 8000:
            text = text[:8000] + "\n...[truncated]..."

        prompt = EXTRACTION_PROMPT.format(text=text)
        response = await call_ollama_text(client, prompt)
        predicates = parse_k_numbers_from_response(response)
        predicates = [k for k in predicates if k != k_number]
        duration = (time.perf_counter() - start) * 1000

        return BenchmarkResult(
            pdf_path=str(pdf_path),
            k_number=k_number,
            method="llm_text",
            predicates=predicates,
            duration_ms=duration,
            raw_response=response[:500],
        )
    except Exception as e:
        return BenchmarkResult(
            pdf_path=str(pdf_path),
            k_number=k_number,
            method="llm_text",
            predicates=[],
            duration_ms=(time.perf_counter() - start) * 1000,
            error=str(e),
        )


async def benchmark_vision_ocr(
    client: httpx.AsyncClient, pdf_path: Path, executor: ThreadPoolExecutor
) -> BenchmarkResult:
    """Benchmark vision OCR extraction - processes pages in parallel."""
    k_number = pdf_path.stem
    start = time.perf_counter()

    try:
        loop = asyncio.get_event_loop()
        images = await loop.run_in_executor(
            executor, pdf_to_images_b64, pdf_path, 3, 200
        )

        if not images:
            raise ValueError("No images extracted from PDF")

        # Process each page in parallel
        tasks = [
            call_ollama_vision(client, [img_b64], VISION_PROMPT) for img_b64 in images
        ]
        all_responses = await asyncio.gather(*tasks)

        all_predicates = []
        for response in all_responses:
            page_k_numbers = parse_k_numbers_from_response(response)
            all_predicates.extend(page_k_numbers)

        # Dedupe while preserving order
        seen = set()
        predicates = []
        for k in all_predicates:
            if k not in seen and k != k_number:
                seen.add(k)
                predicates.append(k)

        duration = (time.perf_counter() - start) * 1000

        return BenchmarkResult(
            pdf_path=str(pdf_path),
            k_number=k_number,
            method="vision_ocr",
            predicates=predicates,
            duration_ms=duration,
            raw_response="\n---\n".join(all_responses)[:500],
        )
    except Exception as e:
        return BenchmarkResult(
            pdf_path=str(pdf_path),
            k_number=k_number,
            method="vision_ocr",
            predicates=[],
            duration_ms=(time.perf_counter() - start) * 1000,
            error=str(e),
        )


def get_text_density(pdf_path: Path) -> float:
    """Get chars per page for a PDF."""
    try:
        text, page_count = extract_text_from_pdf(pdf_path)
        return len(text) / page_count if page_count > 0 else 0
    except:
        return 0


async def select_sample_pdfs(
    pdf_dir: Path, n_text_rich: int, n_empty: int, executor: ThreadPoolExecutor
) -> tuple[list[Path], list[Path]]:
    """Select a mix of text-rich and empty PDFs for benchmarking."""
    all_pdfs = list(pdf_dir.glob("K*.pdf"))

    print(f"Scanning {len(all_pdfs)} PDFs to find samples...")

    # Sample more than needed, then pick randomly
    sample_size = min(len(all_pdfs), 1000)
    candidates = random.sample(all_pdfs, sample_size)

    # Compute densities in parallel using thread pool
    loop = asyncio.get_event_loop()
    density_tasks = [
        loop.run_in_executor(executor, get_text_density, pdf) for pdf in candidates
    ]
    densities = await asyncio.gather(*density_tasks)

    text_rich = []
    empty = []

    for pdf, density in zip(candidates, densities):
        if density >= 500 and len(text_rich) < n_text_rich * 2:
            text_rich.append(pdf)
        elif density < 50 and len(empty) < n_empty * 2:
            empty.append(pdf)

        if len(text_rich) >= n_text_rich * 2 and len(empty) >= n_empty * 2:
            break

    # Random sample from candidates
    text_rich = random.sample(text_rich, min(n_text_rich, len(text_rich)))
    empty = random.sample(empty, min(n_empty, len(empty)))

    return text_rich, empty


def summarize_results(results: list[BenchmarkResult], method: str) -> BenchmarkSummary:
    """Create summary statistics for a method."""
    successful = [r for r in results if r.error is None]
    failed = [r for r in results if r.error is not None]

    avg_duration = (
        sum(r.duration_ms for r in successful) / len(successful) if successful else 0
    )
    total_predicates = sum(len(r.predicates) for r in successful)

    return BenchmarkSummary(
        method=method,
        total_pdfs=len(results),
        successful=len(successful),
        failed=len(failed),
        avg_duration_ms=avg_duration,
        total_predicates_found=total_predicates,
        results=results,
    )


def print_comparison(
    summaries: dict[str, BenchmarkSummary], pdf_paths: list[Path]
) -> None:
    """Print detailed comparison of methods."""
    print("\n" + "=" * 70)
    print("BENCHMARK RESULTS")
    print("=" * 70)

    # Overall stats
    print("\nOverall Performance:")
    print("-" * 70)
    print(f"{'Method':<15} {'Success':<10} {'Avg Time':<15} {'Predicates':<15}")
    print("-" * 70)

    for method, summary in summaries.items():
        print(
            f"{method:<15} {summary.successful}/{summary.total_pdfs:<7} {summary.avg_duration_ms:>10.0f}ms   {summary.total_predicates_found:<15}"
        )

    # Per-PDF comparison
    print("\n" + "-" * 70)
    print("Per-PDF Comparison:")
    print("-" * 70)

    for pdf_path in pdf_paths[:10]:  # Show first 10
        k_number = pdf_path.stem
        density = get_text_density(pdf_path)
        pdf_type = "text" if density >= 500 else "scan"

        print(f"\n{k_number} ({pdf_type}, {density:.0f} chars/pg):")

        for method, summary in summaries.items():
            result = next(
                (r for r in summary.results if Path(r.pdf_path) == pdf_path), None
            )
            if result:
                status = "ERR" if result.error else "OK"
                preds = result.predicates[:3]
                preds_str = ", ".join(preds) + (
                    "..." if len(result.predicates) > 3 else ""
                )
                print(
                    f"  {method:<12}: [{status}] {result.duration_ms:>6.0f}ms | {preds_str or 'none'}"
                )


async def benchmark_pdf(
    client: httpx.AsyncClient,
    pdf_path: Path,
    methods: list[str],
    executor: ThreadPoolExecutor,
) -> dict[str, BenchmarkResult]:
    """Run all benchmark methods for a single PDF in parallel."""
    benchmark_fns = {
        "regex": benchmark_regex,
        "llm_text": benchmark_llm_text,
        "vision_ocr": benchmark_vision_ocr,
    }

    tasks = [benchmark_fns[method](client, pdf_path, executor) for method in methods]
    results_list = await asyncio.gather(*tasks)

    return dict(zip(methods, results_list))


async def run_benchmarks(
    all_pdfs: list[Path],
    methods: list[str],
    concurrency: int = 4,
) -> dict[str, list[BenchmarkResult]]:
    """Run benchmarks on all PDFs with controlled concurrency."""
    results: dict[str, list[BenchmarkResult]] = {m: [] for m in methods}
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient() as client:
        with ThreadPoolExecutor(max_workers=8) as executor:

            async def process_pdf(
                idx: int, pdf_path: Path
            ) -> dict[str, BenchmarkResult]:
                async with semaphore:
                    print(f"[{idx}/{len(all_pdfs)}] {pdf_path.stem}")
                    return await benchmark_pdf(client, pdf_path, methods, executor)

            tasks = [process_pdf(i, pdf_path) for i, pdf_path in enumerate(all_pdfs, 1)]
            pdf_results = await asyncio.gather(*tasks)

            for pdf_result in pdf_results:
                for method, result in pdf_result.items():
                    results[method].append(result)

    return results


async def async_main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark predicate extraction methods"
    )
    parser.add_argument("--pdf-dir", type=Path, default=Path("pdfs"))
    parser.add_argument(
        "--n-text", type=int, default=5, help="Number of text-rich PDFs"
    )
    parser.add_argument(
        "--n-empty", type=int, default=5, help="Number of empty/scanned PDFs"
    )
    parser.add_argument(
        "--methods",
        nargs="+",
        default=["regex", "llm_text"],
        choices=["regex", "llm_text", "vision_ocr"],
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Number of PDFs to process concurrently",
    )
    parser.add_argument("--output", type=Path, help="Save results to JSON file")
    args = parser.parse_args()

    # Select sample PDFs
    with ThreadPoolExecutor(max_workers=8) as executor:
        text_rich, empty = await select_sample_pdfs(
            args.pdf_dir, args.n_text, args.n_empty, executor
        )
    all_pdfs = text_rich + empty

    print(f"\nSelected {len(text_rich)} text-rich + {len(empty)} empty PDFs")
    print(f"Methods to benchmark: {args.methods}")
    print(f"Concurrency: {args.concurrency}\n")

    # Run benchmarks
    results = await run_benchmarks(all_pdfs, args.methods, args.concurrency)

    # Summarize
    summaries = {m: summarize_results(r, m) for m, r in results.items()}
    print_comparison(summaries, all_pdfs)

    # Save results
    if args.output:
        output_data = {
            method: [
                {
                    "pdf": r.pdf_path,
                    "k_number": r.k_number,
                    "predicates": r.predicates,
                    "duration_ms": r.duration_ms,
                    "error": r.error,
                }
                for r in method_results
            ]
            for method, method_results in results.items()
        }
        args.output.write_text(json.dumps(output_data, indent=2))
        print(f"\nResults saved to {args.output}")


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
