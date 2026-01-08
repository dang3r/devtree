#!/usr/bin/env python3
"""
DevTree Data Pipeline Runner

Orchestrates the full pipeline:
1. Fetch FDA JSON and diff against db.json for new/reprocess devices
2. Download PDFs for new devices
3. Extract text and predicates (with OCR fallback)
4. Update db.json
5. Build graph
6. Generate PR report

Usage:
    uv run run_pipeline.py              # Full pipeline
    uv run run_pipeline.py --dry-run    # Show what would be processed
    uv run run_pipeline.py --skip-fetch # Use existing FDA data, process all
    uv run run_pipeline.py --no-ocr     # Disable OCR fallback
"""

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from pipeline.db import (
    DeviceDatabase,
    load_db,
    save_db,
    update_device_from_download,
    update_device_from_extraction,
)
from pipeline.download import download_pdfs
from pipeline.extract import ExtractionResult, extract_all
from pipeline.fetch import (
    FetchResult,
    extract_k_numbers,
    fetch_and_diff_with_db,
    load_existing_data,
)
from pipeline.graph import build_graph, export_cytoscape, export_graph
from pipeline.report import PipelineStats, generate_report_file


def get_project_paths() -> dict[str, Path]:
    """Get standard project paths."""
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data"

    return {
        "root": project_root,
        "data": project_root / "data",
        "pdfs": project_root / "pdfs",
        "text": project_root / "text",
        "fda_json": data_dir / "device-510k.json",
        "db": data_dir / "db.json",
        # Legacy paths (kept for migration/backward compat)
        "predicates": data_dir / "predicates.json",
        "suspicious": data_dir / "suspicious.json",
        "graph": data_dir / "device_graph.json",
        "cytoscape": data_dir / "cytoscape_graph.json",
        "contacts": data_dir / "pmn96cur.txt",
        "company_mappings": data_dir / "company_mappings.json",
        "report": project_root / "pr_description.md",
    }


def update_db_from_results(
    db: DeviceDatabase,
    extraction_results: list[ExtractionResult],
) -> None:
    """Update database from extraction results."""
    for result in extraction_results:
        flags = [f.reason for f in result.flags]
        update_device_from_extraction(
            db,
            result.k_number,
            predicates=result.predicates.predicates,
            extraction_method=result.extraction_method,
            text_length=result.text_metadata.text_length,
            chars_per_page=result.text_metadata.chars_per_page,
            page_count=result.text_metadata.page_count,
            flags=flags,
            extraction_error=result.error,
            ocr_error=result.ocr_error,
        )


def run_pipeline(
    dry_run: bool = False,
    skip_fetch: bool = False,
    k_numbers: list[str] | None = None,
    use_ocr: bool = True,
) -> int:
    """Run the full pipeline. Returns exit code."""
    start_time = time.time()
    paths = get_project_paths()

    # Ensure directories exist
    paths["data"].mkdir(parents=True, exist_ok=True)
    paths["pdfs"].mkdir(parents=True, exist_ok=True)
    paths["text"].mkdir(parents=True, exist_ok=True)

    print("DEVTREE DATA PIPELINE")

    # Step 1: Fetch and diff
    if k_numbers:
        # Manual list provided
        print(f"Using provided K-numbers: {len(k_numbers)}")
        fetch_result = FetchResult(
            new_k_numbers=k_numbers,
            reprocess_k_numbers=[],
            total_in_new=len(k_numbers),
            total_in_existing=0,
            new_count=len(k_numbers),
            reprocess_count=0,
        )
        fda_data = load_existing_data(paths["fda_json"])
        db = load_db(paths["db"])
    elif skip_fetch:
        # Use all devices in existing FDA data
        print("Skipping fetch, using existing FDA data...")
        fda_data = load_existing_data(paths["fda_json"])
        all_k_nums = sorted(extract_k_numbers(fda_data))
        fetch_result = FetchResult(
            new_k_numbers=all_k_nums,
            reprocess_k_numbers=[],
            total_in_new=len(all_k_nums),
            total_in_existing=len(all_k_nums),
            new_count=len(all_k_nums),
            reprocess_count=0,
        )
        db = load_db(paths["db"])
    else:
        print("Step 1: Fetching FDA data...")
        fetch_result, fda_data, db = fetch_and_diff_with_db(
            paths["fda_json"],
            paths["db"],
            reprocess_months=2,
        )

    print()
    total_to_process = fetch_result.new_count + fetch_result.reprocess_count
    print(f"New devices to process: {fetch_result.new_count}")
    print(f"Devices to reprocess: {fetch_result.reprocess_count}")
    print(f"Total to process: {total_to_process}")

    if total_to_process == 0:
        print("\nNo devices to process. Exiting.")
        return 0

    if dry_run:
        print("\n[DRY RUN] Would process these K-numbers:")
        all_to_process = fetch_result.new_k_numbers + fetch_result.reprocess_k_numbers
        for k in all_to_process[:20]:
            is_new = k in fetch_result.new_k_numbers
            print(f"  {k} {'(new)' if is_new else '(reprocess)'}")
        if len(all_to_process) > 20:
            print(f"  ... and {len(all_to_process) - 20} more")
        return 0

    # Step 2: Download PDFs (only for new devices)
    print()
    print("Step 2: Downloading PDFs for new devices...")
    download_summary = download_pdfs(
        fetch_result.new_k_numbers,
        paths["pdfs"],
    )

    # Update db with download results
    for result in download_summary.results:
        update_device_from_download(
            db,
            result.k_number,
            success=result.status == "success",
            error=result.error,
        )

    # Save db after downloads
    save_db(db, paths["db"])

    # Step 3: Extract text and predicates (new + reprocess)
    print()
    print("Step 3: Extracting text and predicates...")
    all_to_extract = fetch_result.new_k_numbers + fetch_result.reprocess_k_numbers
    extraction_results, extraction_summary = extract_all(
        all_to_extract,
        paths["pdfs"],
        paths["text"],
        use_ocr_fallback=use_ocr,
    )

    # Update db with extraction results
    update_db_from_results(db, extraction_results)
    save_db(db, paths["db"])

    # Step 4: Build graph
    print()
    print("Step 4: Building graph...")
    graph = build_graph(
        paths["fda_json"],
        paths["db"],  # Use db.json instead of predicates.json
        paths["contacts"] if paths["contacts"].exists() else None,
        paths["company_mappings"] if paths["company_mappings"].exists() else None,
        use_db_format=True,  # Use new db.json format
    )
    export_graph(graph, paths["graph"])
    export_cytoscape(graph, paths["cytoscape"])

    # Step 5: Generate report
    print()
    print("Step 5: Generating report...")
    end_time = time.time()
    stats = PipelineStats(
        started_at=datetime.fromtimestamp(start_time, timezone.utc).isoformat(),
        completed_at=datetime.fromtimestamp(end_time, timezone.utc).isoformat(),
        duration_seconds=end_time - start_time,
    )

    report = generate_report_file(
        fetch_result,
        download_summary,
        extraction_results,
        extraction_summary,
        fda_data,
        stats,
        str(paths["report"]),
    )

    # Final summary
    print()
    print("=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print(f"Duration: {stats.duration_seconds:.1f}s")
    print(f"New devices: {fetch_result.new_count}")
    print(f"Reprocessed: {fetch_result.reprocess_count}")
    print(f"PDFs downloaded: {download_summary.success}")
    print(f"Extractions: {extraction_summary.success}")
    print(f"OCR used: {extraction_summary.ocr_used}")
    print(f"Flagged: {extraction_summary.flagged}")
    print(f"Report: {paths['report']}")
    print(f"Database: {paths['db']}")
    print()

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the DevTree data pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without making changes",
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Skip FDA fetch, process all devices in existing data",
    )
    parser.add_argument(
        "--k-numbers",
        nargs="+",
        help="Process specific K-numbers instead of fetching",
    )
    parser.add_argument(
        "--no-ocr",
        action="store_true",
        help="Disable OCR fallback for sparse PDFs",
    )

    args = parser.parse_args()

    return run_pipeline(
        dry_run=args.dry_run,
        skip_fetch=args.skip_fetch,
        k_numbers=args.k_numbers,
        use_ocr=not args.no_ocr,
    )


if __name__ == "__main__":
    sys.exit(main())
