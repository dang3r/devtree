"""
FDA Device Extraction Pipeline

A pipeline that:
1. Downloads FDA device registry JSON
2. Identifies new devices and downloads their PDFs
3. Extracts text using PyMuPDF and Tesseract
4. Extracts predicates using regex and LLM
"""

from collections import defaultdict
from functools import partial
import json
import pathlib
import random
import time
from concurrent.futures import (
    Executor,
    ThreadPoolExecutor,
    ProcessPoolExecutor,
    as_completed,
)
from pathlib import Path
from datetime import datetime
from typing import Any, Callable, TypeVar

from pydantic import BaseModel

from extract import ExtractionResult, PREDICATE_EXTRACTORS
from aggregate import aggregate_predicates, load_existing_predicates
from lib import (
    RAWTEXT_PATH,
    TESSERACT_TEXT_PATH,
    MINISTRAL3_3B_PATH,
    PDF_PATH,
)
from download import download_pdf_sync, new_fda_devices
from textify import TEXT_EXTRACTORS
from graph import build_all_graphs
import argparse


T = TypeVar("T")


class StageResult(BaseModel):
    """Result of a pipeline stage execution."""

    succeeded: list
    failed: list
    skipped: list
    elapsed_seconds: float

    model_config = {"arbitrary_types_allowed": True}
    results: list[Any]

    def print_summary(self, stage_name: str) -> None:
        total = len(self.succeeded) + len(self.failed) + len(self.skipped)
        print(f"\n{'='*50}")
        print(f"Stage: {stage_name}")
        print(f"  Total:       {total}")
        print(f"  ✓ Succeeded: {len(self.succeeded)}")
        print(f"  ✗ Failed:    {len(self.failed)}")
        print(f"  ○ Skipped:   {len(self.skipped)}")
        print(f"  ⏱ Time:      {self.elapsed_seconds:.1f}s")
        if self.failed:
            print(f"  Failed IDs:  {[f[0] for f in self.failed[:5]]}")
        print(f"{'='*50}\n")


def run_stage(
    stage_name: str,
    items: list[str],
    task_fn: Callable[[str], T],
    executor: Executor,
    skip_fn: Callable[[str], bool] = lambda _: False,
) -> StageResult:
    """
    Run a pipeline stage with automatic summary.

    Args:
        stage_name: Name for logging
        items: List of IDs to process
        task_fn: Function that takes an ID and returns a result (or raises)
        executor: Executor to use (will be shutdown after stage completes)
        skip_fn: Function to check if item should be skipped (default: never skip)
    """
    start = time.time()
    succeeded: list[tuple[str, Any]] = []
    failed: list[tuple[str, str]] = []
    skipped: list[str] = []

    # Filter skipped items
    to_process = []
    for item_id in items:
        if skip_fn(item_id):
            skipped.append(item_id)
        else:
            to_process.append(item_id)

    try:
        futures = {executor.submit(task_fn, item_id): item_id for item_id in to_process}

        for idx, future in enumerate(as_completed(futures)):
            if idx % max(1, len(futures) // 10) == 0:
                print(
                    f"Stage {stage_name}: {idx} of {len(futures)}, speed={idx / (time.time() - start):.1f} items/s"
                )
            item_id = futures[future]
            try:
                result = future.result()
                if result.error:
                    failed.append((item_id, result))
                else:
                    succeeded.append((item_id, result))
            except Exception as e:
                import traceback

                print(traceback.format_exc())

                failed.append((item_id, str(e)))
    finally:
        executor.shutdown(wait=True)

    stage_result = StageResult(
        succeeded=succeeded,
        failed=failed,
        skipped=skipped,
        elapsed_seconds=time.time() - start,
        results=succeeded + failed + skipped,
    )
    stage_result.print_summary(stage_name)
    return stage_result


# ---------------------------------------------------------------------------
# Picklable wrapper functions for ProcessPoolExecutor
# ---------------------------------------------------------------------------
def _extract_predicate_task(
    item: tuple[str, Path, str], method: str
) -> ExtractionResult | None:
    """Wrapper that unpacks tuple args and calls the appropriate extractor."""
    from extract import PREDICATE_EXTRACTORS

    device_id, text_path, source = item
    return PREDICATE_EXTRACTORS[method].func(device_id, text_path, source)


# ---------------------------------------------------------------------------
# Main Flow
# ---------------------------------------------------------------------------


def textify_stages(device_ids: list[str], text_methods: list[str]) -> list[StageResult]:
    if not text_methods:
        return [
            StageResult(
                succeeded=[],
                failed=[],
                skipped=[],
                elapsed_seconds=0,
                results=[],
            )
        ]

    workers = len(text_methods)
    with ThreadPoolExecutor(max_workers=workers) as stage_executor:
        future_srs = []
        for method in text_methods:
            if method not in TEXT_EXTRACTORS:
                raise ValueError(f"Unknown text method: {method}")
            config = TEXT_EXTRACTORS[method]
            executor = (
                ProcessPoolExecutor(max_workers=config.max_workers)
                if config.executor_type == "process"
                else ThreadPoolExecutor(max_workers=config.max_workers)
            )
            future = stage_executor.submit(
                run_stage,
                stage_name=config.name,
                items=device_ids,
                task_fn=config.func,
                executor=executor,
            )
            future_srs.append(future)

    textify_srs = []
    for future in as_completed(future_srs):
        textify_srs.append(future.result())

    return textify_srs


def extract_predicates_stages(
    work_items: list[tuple[str, Path, str]], predicate_methods: list[str]
) -> list[ExtractionResult]:
    extract_results = []
    assert all(method in PREDICATE_EXTRACTORS for method in predicate_methods)
    for method in predicate_methods:
        config = PREDICATE_EXTRACTORS[method]
        executor = (
            ProcessPoolExecutor(max_workers=config.max_workers)
            if config.executor_type == "process"
            else ThreadPoolExecutor(max_workers=config.max_workers)
        )
        results = run_stage(
            stage_name=config.name,
            items=work_items,
            task_fn=partial(_extract_predicate_task, method=method),
            executor=executor,
        )
        extract_results.extend(results.succeeded)
    return extract_results


def fda_extraction_pipeline(
    pdf_dir: Path = PDF_PATH,
    text_methods=list[str],
    predicate_methods=list[str],
    device_ids: list[str] = [],
):
    job_path = pathlib.Path("jobs") / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    job_path.mkdir(parents=True, exist_ok=True)
    for path in [RAWTEXT_PATH, TESSERACT_TEXT_PATH, MINISTRAL3_3B_PATH, PDF_PATH]:
        path.mkdir(parents=True, exist_ok=True)

    # 1. Download PDFs
    download_result = run_stage(
        stage_name="Download PDFs",
        items=device_ids,
        task_fn=lambda did: download_pdf_sync(did, pdf_dir),
        executor=ThreadPoolExecutor(max_workers=3),
    )
    device_ids_with_pdfs = [result.device_id for s, result in download_result.succeeded]

    # 2. Extract text
    textify_srs = textify_stages(
        device_ids=device_ids_with_pdfs,
        text_methods=text_methods,
    )
    work_items = []
    for sr in textify_srs:
        results = sr.succeeded
        for did, result in results:
            work_items.append((did, result.filepath, result.type()))

    # 3. Extract predicates
    extract_results = extract_predicates_stages(work_items, predicate_methods)

    # 5. Agggregate local results
    sm_dict = defaultdict(list)
    extract_results = [x[1] for x in extract_results]
    for result in extract_results:
        key = result.method + "_" + result.source
        sm_dict[key].append(result.model_dump())
    for key, results in sm_dict.items():
        with open(job_path / f"predicates_{key}.json", "w") as f:
            json.dump(results, f, indent=2)

    # 5. Merge with existing predicates
    existing_predicates = load_existing_predicates()
    aggregated_results = aggregate_predicates(existing_predicates + extract_results)
    with open(job_path / "aggregated_predicates.json", "w") as f:
        json.dump(aggregated_results, f, indent=2)

    with open(job_path / "final_predicates.json", "w") as f:
        aggregated_results = dict(
            sorted(aggregated_results.items(), key=lambda x: x[0])
        )
        json.dump(aggregated_results, f, indent=2)

    # 6. Build the graphs
    build_all_graphs(aggregated_results, job_path)

    # Compare new aggregated results with existing predicates.
    existing_list = load_existing_predicates()
    existing_dict = {e.device_id: e for e in existing_list}
    predicate_diff = {}
    for device_id, device_data in aggregated_results.items():
        new_preds = set(device_data["predicates"])
        if device_id in existing_dict:
            old_preds = set(existing_dict[device_id].predicates)
            if old_preds != new_preds:
                predicate_diff[device_id] = {
                    "old": existing_dict[device_id].model_dump(),
                    "new": device_data,
                }
    with open(job_path / "predicate_diff.json", "w") as f:
        json.dump(predicate_diff, f, indent=2)


if __name__ == "__main__":
    text_methods = ["tesseract", "ollama", "pymupdf"]
    predicate_methods = ["regex", "ollama"]
    args = argparse.ArgumentParser(description="Run the FDA extraction pipeline")
    args.add_argument("command", type=str)
    args = args.parse_args()

    if args.command == "new":
        device_ids = new_fda_devices()
        fda_extraction_pipeline(
            device_ids=device_ids,
            text_methods=["pymupdf", "tesseract"],
            predicate_methods=["regex", "openrouter"],
        )
    elif args.command == "all":
        device_ids = [p.stem for p in PDF_PATH.glob("*.pdf")]
        fda_extraction_pipeline(
            device_ids=device_ids,
            text_methods=["pymupdf", "tesseract"],
            predicate_methods=["regex"],
        )
    elif args.command == "test":
        device_ids = random.sample([p.stem for p in PDF_PATH.glob("*.pdf")], 10)
        fda_extraction_pipeline(
            device_ids=device_ids,
            text_methods=["pymupdf", "tesseract", "ollama"],
            predicate_methods=["regex", "ollama"],
        )
    elif args.command == "openrouter":
        device_ids = random.sample([p.stem for p in PDF_PATH.glob("*.pdf")], 10)
        # device_ids = ["K203287", "K232891", "K202050", "K232891"]
        fda_extraction_pipeline(
            device_ids=device_ids,
            text_methods=["pymupdf", "tesseract"],
            predicate_methods=["regex", "openrouter"],
        )
