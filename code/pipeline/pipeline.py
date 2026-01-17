"""
FDA Device Extraction Pipeline

A pipeline that:
1. Downloads FDA device registry JSON
2. Identifies new devices and downloads their PDFs
3. Extracts text using PyMuPDF and Tesseract
4. Extracts predicates using regex and LLM
"""

from collections import defaultdict
import io
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
from datetime import datetime, timedelta
from typing import Any, Callable, TypeVar

import requests
import zipfile
from pydantic import BaseModel

from extract import ExtractionResult
from lib import (
    DATA_PATH,
    PREDICATES_CLAUDECODE_PATH,
    RAWTEXT_PATH,
    TESSERACT_TEXT_PATH,
    MINISTRAL3_3B_PATH,
    PDF_PATH,
)
from download import download_pdf_sync
from textify import extract_text
from textify_tesseract import extract_text as extract_text_tesseract
from ocr_pdf import ocr_pdf
import argparse


T = TypeVar("T")


FDA_JSON_URL = (
    "https://download.open.fda.gov/device/510k/device-510k-0001-of-0001.json.zip"
)


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
            if idx % (len(futures) // 10) == 0:
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


EXTRACTION_PRIORITY = {
    ("human", "raw"): -1,
    ("claude_code", "raw"): 0,
    ("ministral3b_3b", "ministral"): 1,
    ("ministral3b_3b", "tesseract"): 2,
    ("ministral3b_3b", "raw"): 3,
    ("regex", "ministral"): 4,
    ("regex", "tesseract"): 5,
    ("regex", "raw"): 6,
}
NEW_EXTRACTION_PRIORITY = {
    "human_raw": 0,
    "claude_code_raw": 1,
    "ollama_ministral-3:3b_ministral": 2,
    "ollama_ministral-3:3b_tesseract": 4,
    "ollama_ministral-3:3b_pymupdf": 3,
    "regex_ministral": 6,
    "regex_tesseract": 8,
    "regex_pymupdf": 7,
}


def aggregate_predicates(extract_results: list[ExtractionResult]) -> dict[str, dict]:
    by_device: dict[str, list[tuple[int, Any]]] = {}

    for _input, extract_result in extract_results:
        if extract_result and not extract_result.error:
            key = extract_result.type
            priority = NEW_EXTRACTION_PRIORITY.get(key, 99)
            if extract_result.device_id not in by_device:
                by_device[extract_result.device_id] = []
            by_device[extract_result.device_id].append((priority, extract_result))

    aggregated = {}
    for device_id, entries in by_device.items():
        best = min(entries, key=lambda x: x[0])[1]
        aggregated[device_id] = {
            "predicates": best.predicates,
            "method": best.method,
            "source": best.source,
            "type": best.type,
        }

    # ensure dict keys are sorted by device_id
    aggregated = dict(sorted(aggregated.items(), key=lambda x: x[0]))
    return aggregated


# ---------------------------------------------------------------------------
# Picklable wrapper functions for ProcessPoolExecutor
# ---------------------------------------------------------------------------
def _extract_regex_task(item: tuple[str, Path, str]) -> ExtractionResult | None:
    """Wrapper for extract_predicates_from_text_regex that unpacks tuple args."""
    from extract import extract_predicates_from_text_regex

    device_id, text_path, source = item
    return extract_predicates_from_text_regex(device_id, text_path, source)


def _extract_ollama_task(item: tuple[str, Path, str]) -> ExtractionResult | None:
    """Wrapper for extract_predicates_from_text_ollama that unpacks tuple args."""
    from extract import extract_predicates_from_text_ollama

    device_id, text_path, source = item
    return extract_predicates_from_text_ollama(device_id, text_path, source)


# ---------------------------------------------------------------------------
# Download & Identification Tasks
# ---------------------------------------------------------------------------


def download_device_json(url: str = FDA_JSON_URL) -> list[dict]:
    response = requests.get(
        url,
        timeout=60,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.38 11"
        },
    )
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
        with zip_file.open("device-510k-0001-of-0001.json") as f:
            data = json.load(f)
    return data


def is_old_device(device: dict) -> bool:
    import datetime
    from datetime import timezone

    threshold_date = datetime.datetime.now(timezone.utc) - timedelta(days=365)
    device_date = datetime.datetime.strptime(
        device["decision_date"], "%Y-%m-%d"
    ).replace(tzinfo=timezone.utc)
    return device_date <= threshold_date


def is_recent_device(device: dict) -> bool:
    import datetime
    from datetime import timezone

    threshold_date = datetime.datetime.now(timezone.utc) - timedelta(days=30)
    device_date = datetime.datetime.strptime(
        device["decision_date"], "%Y-%m-%d"
    ).replace(tzinfo=timezone.utc)
    return device_date >= threshold_date


def pdf_data() -> dict:
    from lib import PDF_DATA_PATH

    return json.load(open(PDF_DATA_PATH))


def identify_new_devices(
    fda_data: dict,
) -> list[str]:
    # Determine what devices to download
    fda_device_ids = [d["k_number"] for d in fda_data["results"]]
    device_ids_1yold = [d["k_number"] for d in fda_data["results"] if is_old_device(d)]
    device_ids_recent = [
        d["k_number"] for d in fda_data["results"] if is_recent_device(d)
    ]
    device_ids_with_no_summary = pdf_data()["no_summary"]
    device_ids_with_local_pdfs = [p.stem for p in Path("pdfs").glob("*.pdf")]

    to_download = (
        set(fda_device_ids)
        - set(device_ids_with_no_summary)
        - set(device_ids_1yold)
        - set(device_ids_with_local_pdfs)
    ) | (set(device_ids_recent) - set(device_ids_with_local_pdfs))

    print("Found", len(to_download), "devices to download")
    return list(to_download)


def new_fda_devices(device_json_url: str = FDA_JSON_URL) -> list[str]:
    print("Downloading device registry...")
    fda_data = download_device_json(device_json_url)
    new_devices = identify_new_devices(fda_data)
    print(f"Found {len(new_devices)} new devices to process")
    return new_devices


# ---------------------------------------------------------------------------
# Main Flow
# ---------------------------------------------------------------------------


def existing_predicates_aggregate() -> dict:
    # Read these files and merge them into a single dict
    base = pathlib.Path(__file__).parent.parent.parent / "data" / "gt"
    filepaths = [
        (base / "predicates_overrides.json", "human", "raw", "human_raw"),
        (base / "predicates_claudecode.json", "claude_code", "raw", "claude_code_raw"),
        (
            base / "predicates_regex_ministral3_3b.json",
            "regex",
            "ministral3b",
            "regex_ministral3b",
        ),
        (base / "predicates_regex_rawtext.json", "regex", "raw", "regex_pymupdf"),
    ]
    aggregated = {}
    for filepath, method, source, type in filepaths[::-1]:
        with open(filepath, "r") as f:
            data = json.load(f)
        for key, value in data.items():
            aggregated[key] = {
                "predicates": value["predicates"],
                "method": method,
                "source": source,
                "type": type,
            }
    return aggregated

    # read data/claude_code


def textify_stages(device_ids, text_methods):
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
        if "pymupdf" in text_methods:
            textify_sr = stage_executor.submit(
                run_stage,
                stage_name="Extract Text (PyMuPDF)",
                items=device_ids,
                task_fn=extract_text,
                executor=ProcessPoolExecutor(max_workers=4),
            )
            future_srs.append(textify_sr)
        if "tesseract" in text_methods:
            tesseract_future = stage_executor.submit(
                run_stage,
                stage_name="Extract Text (Tesseract)",
                items=device_ids,
                task_fn=extract_text_tesseract,
                executor=ProcessPoolExecutor(max_workers=4),
            )
            future_srs.append(tesseract_future)
        if "ollama" in text_methods:
            ollama_future = stage_executor.submit(
                run_stage,
                stage_name="Extract Text (Ollama)",
                items=device_ids,
                task_fn=lambda did: ocr_pdf(did, MINISTRAL3_3B_PATH / f"{did}.txt"),
                executor=ThreadPoolExecutor(max_workers=1),
            )
            future_srs.append(ollama_future)

    textify_srs = []
    for future in as_completed(future_srs):
        textify_srs.append(future.result())

    return textify_srs


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
    assert all(
        text_method in ["tesseract", "ollama", "pymupdf"]
        for text_method in text_methods
    )

    # 1. Download PDFS for new devices
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
        results = sr.succeeded + sr.skipped
        for did, result in results:
            if "pymupdf" in str(result.filepath):
                source = "pymupdf"
            elif "tesseract" in str(result.filepath):
                source = "tesseract"
            elif "ministral" in str(result.filepath):
                source = "ministral"
            else:
                raise ValueError(f"Unknown source: {result.filepath}")
            work_items.append((did, result.filepath, source))

    # 3. Extract predicates. Regex is fast so no need to parallelize
    extract_results = []
    if "regex" in predicate_methods:
        regex_results = run_stage(
            stage_name="Extract Predicates (Regex)",
            items=work_items,
            task_fn=_extract_regex_task,
            executor=ProcessPoolExecutor(),
        )
        extract_results.extend(regex_results.succeeded)
    if "ollama" in predicate_methods:
        ollama_results = run_stage(
            stage_name="Extract Predicates (Ollama)",
            items=work_items,
            task_fn=_extract_ollama_task,
            executor=ThreadPoolExecutor(max_workers=4),
        )
        extract_results.extend(ollama_results.succeeded)

    # 5. Agggregate local results
    sm_dict = defaultdict(list)
    for _, result in extract_results:
        key = result.method + "_" + result.source
        sm_dict[key].append(result.model_dump())
    for key, results in sm_dict.items():
        with open(job_path / f"predicates_{key}.json", "w") as f:
            json.dump(results, f, indent=2)

    #
    aggregated_results = aggregate_predicates(extract_results)
    with open(job_path / "aggregated_predicates.json", "w") as f:
        json.dump(aggregated_results, f, indent=2)

    # 5. Merge with existing predicates
    existing_predicates = existing_predicates_aggregate()
    for device_id, data in aggregated_results.items():
        if device_id not in existing_predicates:
            existing_predicates[device_id] = data
        elif device_id in existing_predicates:
            existing_priority = EXTRACTION_PRIORITY.get(
                (
                    existing_predicates[device_id]["method"],
                    existing_predicates[device_id]["source"],
                ),
                99,
            )
            new_priority = EXTRACTION_PRIORITY.get((data["method"], data["source"]), 99)
            if new_priority < existing_priority:
                existing_predicates[device_id]["predicates"] = data["predicates"]

    with open(job_path / "final_predicates.json", "w") as f:
        # sort by device_id
        existing_predicates = dict(
            sorted(existing_predicates.items(), key=lambda x: x[0])
        )
        json.dump(existing_predicates, f, indent=2)


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    text_methods = ["tesseract", "ollama", "pymupdf"]
    predicate_methods = ["regex", "ollama"]
    args = argparse.ArgumentParser(description="Run the FDA extraction pipeline")
    args.add_argument("command", type=str, choices=["new", "all", "extract"])
    args = args.parse_args()

    if args.command == "new":
        device_ids = new_fda_devices()
        fda_extraction_pipeline(
            device_ids=device_ids,
            text_methods=text_methods,
            predicate_methods=predicate_methods,
        )
    elif args.command == "all":
        device_ids = [p.stem for p in PDF_PATH.glob("*.pdf")]
        fda_extraction_pipeline(
            device_ids=device_ids,
            text_methods=["pymupdf", "tesseract"],
            predicate_methods=["regex"],
        )
    elif args.command == "extract":
        device_ids = random.sample([p.stem for p in PDF_PATH.glob("*.pdf")], 10)
        fda_extraction_pipeline(
            device_ids=device_ids,
            text_methods=["pymupdf", "tesseract", "ollama"],
            predicate_methods=["regex", "ollama"],
        )
