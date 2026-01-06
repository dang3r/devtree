"""
Extract predicates from all cached text files.

Uses the text/ folder to extract K-number predicates without re-processing PDFs.
"""

import json
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel
from tqdm import tqdm


K_NUMBER_PATTERN = re.compile(r"K\d{6}")


class PredicateResult(BaseModel):
    """Predicate extraction result for a single device."""

    k_number: str
    predicates: list[str]
    all_k_numbers_found: list[str]
    text_length: int
    error: str | None = None


def extract_k_numbers(text: str) -> list[str]:
    """Find all unique K-numbers in text, preserving order."""
    matches = K_NUMBER_PATTERN.findall(text)
    seen = set()
    unique = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            unique.append(m)
    return unique


def process_text_file(text_path: Path) -> PredicateResult:
    """Extract predicates from a single text file."""
    k_number = text_path.stem

    try:
        text = text_path.read_text()
        all_k_numbers = extract_k_numbers(text)

        # Filter out the device's own K-number
        predicates = [k for k in all_k_numbers if k != k_number]

        return PredicateResult(
            k_number=k_number,
            predicates=predicates,
            all_k_numbers_found=all_k_numbers,
            text_length=len(text),
        )
    except Exception as e:
        return PredicateResult(
            k_number=k_number,
            predicates=[],
            all_k_numbers_found=[],
            text_length=0,
            error=str(e),
        )


def main(
    text_dir: Path = Path("text"),
    output_path: Path = Path("predicates.json"),
    workers: int = 8,
) -> None:
    """Extract predicates from all text files."""
    # Find all text files (exclude manifest.json)
    text_files = sorted(text_dir.glob("*.txt"))
    total = len(text_files)
    print(f"Found {total:,} text files")

    results: dict[str, dict] = {}
    success = 0
    with_predicates = 0
    total_predicates = 0
    errors = 0

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_text_file, f): f for f in text_files}

        with tqdm(total=total, desc="Extracting predicates") as pbar:
            for future in as_completed(futures):
                result = future.result()
                results[result.k_number] = {
                    "predicates": result.predicates,
                    "predicate_count": len(result.predicates),
                    "text_length": result.text_length,
                }

                if result.error:
                    errors += 1
                    results[result.k_number]["error"] = result.error
                else:
                    success += 1
                    if result.predicates:
                        with_predicates += 1
                        total_predicates += len(result.predicates)

                pbar.update(1)

    # Save results
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_devices": total,
        "success": success,
        "errors": errors,
        "with_predicates": with_predicates,
        "without_predicates": success - with_predicates,
        "total_predicate_references": total_predicates,
        "devices": results,
    }

    output_path.write_text(json.dumps(output, indent=2))

    # Summary
    print("\n" + "=" * 60)
    print("PREDICATE EXTRACTION COMPLETE")
    print("=" * 60)
    print(f"\nTotal devices: {total:,}")
    print(f"Success: {success:,}")
    print(f"Errors: {errors:,}")
    print(f"\nDevices with predicates: {with_predicates:,}")
    print(f"Devices without predicates: {success - with_predicates:,}")
    print(f"Total predicate references: {total_predicates:,}")
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
