"""
FDA Device Extraction Pipeline

A Prefect-based ETL pipeline that:
1. Downloads FDA device registry JSON
2. Identifies new devices and downloads their PDFs
3. Extracts text using regex, LLM, or OCR+LLM fallback
4. Merges results with previous extractions
5. Generates the final dataset
"""

import io
import json
import pathlib
import re
import hashlib
from pathlib import Path
from datetime import timedelta
from typing import Any
import zipfile

import requests
from prefect import flow, task
from prefect.tasks import task_input_hash
from prefect.task_runners import ThreadPoolTaskRunner


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_PDF_DIR = Path("./pdfs")
DEFAULT_DATA_DIR = Path("./data")
MAX_DOWNLOAD_WORKERS = 10

FDA_JSON_URL = (
    "https://download.open.fda.gov/device/510k/device-510k-0001-of-0001.json.zip"
)


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


@task
def load_existing_devices(path: Path) -> set[str]:
    """Load device IDs we've already processed."""
    if not path.exists():
        return set()

    with open(path, "r") as f:
        data = json.load(f)

    return set(data.get("processed_ids", []))


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


@task(retries=3, retry_delay_seconds=30)
def download_pdf(device: dict, output_dir: Path) -> Path:
    """Download PDF for a single device, return local path."""
    device_id = device.get("k_number", "unknown")
    pdf_url = device.get("pdf_url")

    if not pdf_url:
        raise ValueError(f"No PDF URL for device {device_id}")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{device_id}.pdf"

    # Skip if already downloaded
    if output_path.exists():
        return output_path

    response = requests.get(pdf_url, timeout=120)
    response.raise_for_status()

    with open(output_path, "wb") as f:
        f.write(response.content)

    return output_path


# ---------------------------------------------------------------------------
# Text Extraction Tasks
# ---------------------------------------------------------------------------


@task(
    cache_key_fn=task_input_hash,
    cache_expiration=timedelta(days=30),
)
def extract_pdf_text(pdf_path: Path) -> str:
    """Extract raw text from PDF using pdfplumber."""
    import pdfplumber

    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

    return "\n\n".join(text_parts)


@task
def extract_with_regex(text: str, device: dict) -> dict[str, Any] | None:
    """
    Attempt regex-based extraction.
    Returns None if no matches found.
    """
    results = {}

    # Example patterns - customize for your FDA documents
    patterns = {
        "predicate_device": r"predicate\s+device[:\s]+([A-Z]?\d{6,7})",
        "device_name": r"device\s+name[:\s]+([^\n]+)",
        "manufacturer": r"manufacturer[:\s]+([^\n]+)",
        "submission_date": r"submission\s+date[:\s]+(\d{1,2}/\d{1,2}/\d{4})",
    }

    for field, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            results[field] = match.group(1).strip()

    # Return None if we didn't extract enough useful data
    if len(results) < 2:
        return None

    return results


def _get_pdf_hash(pdf_path: Path) -> str:
    """Compute hash of PDF file for cache key."""
    with open(pdf_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def cache_by_pdf_hash(context, parameters):
    """Cache key based on PDF content hash."""
    pdf_path = parameters.get("pdf_path")
    if pdf_path and Path(pdf_path).exists():
        return _get_pdf_hash(Path(pdf_path))
    return task_input_hash(context, parameters)


@task(
    cache_key_fn=cache_by_pdf_hash,
    cache_expiration=timedelta(days=30),
    retries=2,
    retry_delay_seconds=5,
)
def extract_with_llm(text: str, device: dict, pdf_path: Path) -> dict[str, Any] | None:
    """
    Attempt local LLM extraction.
    Returns None if unsuccessful.

    Assumes a local Ollama instance or similar.
    """
    import ollama

    device_id = device.get("k_number", "unknown")

    prompt = f"""Extract the following fields from this FDA 510(k) document.
Return JSON only, no other text.

Fields to extract:
- predicate_device: The K-number of the predicate device
- device_name: The name of the device
- manufacturer: The manufacturer name
- intended_use: Brief description of intended use
- submission_date: The submission date

Document text:
{text[:8000]}

JSON:"""

    try:
        response = ollama.chat(
            model="llama3.2",
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.1},
        )

        content = response["message"]["content"]

        # Try to parse JSON from response
        json_match = re.search(r"\{[^{}]+\}", content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())

        return None

    except Exception as e:
        print(f"LLM extraction failed for {device_id}: {e}")
        return None


@task(
    cache_key_fn=cache_by_pdf_hash,
    cache_expiration=timedelta(days=30),
    retries=2,
)
def extract_with_ocr_llm(pdf_path: Path, device: dict) -> dict[str, Any]:
    """
    Fallback: OCR the PDF then run LLM extraction.
    Used when text extraction fails.
    """
    import pytesseract
    from pdf2image import convert_from_path

    device_id = device.get("k_number", "unknown")

    # Convert PDF to images and OCR
    images = convert_from_path(pdf_path, dpi=200)
    ocr_texts = []

    for i, image in enumerate(images[:10]):  # Limit pages for performance
        text = pytesseract.image_to_string(image)
        ocr_texts.append(text)

    full_text = "\n\n".join(ocr_texts)

    # Now run LLM extraction on OCR text
    result = extract_with_llm.fn(full_text, device, pdf_path)

    if result:
        return result

    # Return minimal result if all else fails
    return {
        "device_id": device_id,
        "extraction_failed": True,
        "raw_text_length": len(full_text),
    }


@task
def run_extraction_pipeline(
    pdf_path: Path,
    text: str,
    device: dict,
) -> dict[str, Any]:
    """
    Try extraction methods in order:
    1. Regex
    2. LLM
    3. OCR + LLM (fallback)

    Returns result with extraction_type field.
    """
    device_id = device.get("k_number", "unknown")

    # Try regex first (fastest)
    result = extract_with_regex.fn(text, device)
    if result:
        return {
            "extraction_type": "regex",
            "device_id": device_id,
            "device": device,
            **result,
        }

    # Try LLM extraction
    result = extract_with_llm.fn(text, device, pdf_path)
    if result:
        return {
            "extraction_type": "llm",
            "device_id": device_id,
            "device": device,
            **result,
        }

    # Fallback to OCR + LLM
    result = extract_with_ocr_llm.fn(pdf_path, device)
    return {
        "extraction_type": "ocr_llm",
        "device_id": device_id,
        "device": device,
        **result,
    }


# ---------------------------------------------------------------------------
# Aggregation & Merge Tasks
# ---------------------------------------------------------------------------


@task
def group_by_extraction_type(
    results: list[dict[str, Any]],
) -> dict[str, list[dict]]:
    """Group extraction results by their extraction_type."""
    grouped: dict[str, list[dict]] = {}

    for r in results:
        ext_type = r.get("extraction_type", "unknown")
        grouped.setdefault(ext_type, []).append(r)

    return grouped


@task
def load_previous_results(path: Path) -> dict[str, Any]:
    """Load previously extracted/merged results."""
    if not path.exists():
        return {"devices": {}, "metadata": {}}

    with open(path, "r") as f:
        return json.load(f)


@task
def merge_results(
    previous: dict[str, Any],
    new_grouped: dict[str, list[dict]],
) -> dict[str, Any]:
    """Merge new extraction results with previous results."""
    merged = previous.copy()
    devices = merged.setdefault("devices", {})

    for ext_type, results in new_grouped.items():
        for result in results:
            device_id = result.get("device_id")
            if not device_id:
                continue

            # Store or update device extraction
            if device_id not in devices:
                devices[device_id] = result
            else:
                # Prefer certain extraction types over others
                priority = {"regex": 1, "llm": 2, "ocr_llm": 3}
                existing_priority = priority.get(
                    devices[device_id].get("extraction_type"), 99
                )
                new_priority = priority.get(ext_type, 99)

                if new_priority < existing_priority:
                    devices[device_id] = result

    return merged


@task
def save_processed_ids(
    existing_ids: set[str],
    new_devices: list[dict],
    path: Path,
    id_field: str = "k_number",
):
    """Update the list of processed device IDs."""
    all_ids = existing_ids | {d.get(id_field) for d in new_devices if d.get(id_field)}

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump({"processed_ids": list(all_ids)}, f, indent=2)


@task
def generate_final_dataset(
    merged: dict[str, Any],
    output_path: Path,
) -> Path:
    """Selectively merge and write final dataset."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build final dataset structure
    final = {
        "total_devices": len(merged.get("devices", {})),
        "extraction_summary": {},
        "devices": [],
    }

    # Summarize by extraction type
    for device_id, data in merged.get("devices", {}).items():
        ext_type = data.get("extraction_type", "unknown")
        final["extraction_summary"].setdefault(ext_type, 0)
        final["extraction_summary"][ext_type] += 1

        # Add cleaned device record
        final["devices"].append(
            {
                "device_id": device_id,
                "extraction_type": ext_type,
                "predicate_device": data.get("predicate_device"),
                "device_name": data.get("device_name"),
                "manufacturer": data.get("manufacturer"),
                "intended_use": data.get("intended_use"),
                "submission_date": data.get("submission_date"),
            }
        )

    with open(output_path, "w") as f:
        json.dump(final, f, indent=2)

    return output_path


# ---------------------------------------------------------------------------
# Main Flow
# ---------------------------------------------------------------------------


async def run_extract_tasks(device_ids: list[str]):
    from extract import (
        extract_predicates_from_text_regex,
        extract_predicates_from_text_ollama,
    )
    import asyncio
    from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

    loop = asyncio.get_event_loop()
    thread_pool = ThreadPoolExecutor(max_workers=4)  # GPU tasks
    process_pool = ProcessPoolExecutor(max_workers=4)  # Tesseract

    text_files = pathlib.Path("../../text").rglob("*.txt")
    # first 20 text files
    text_files = list(text_files)[:20]
    futures = []
    for text_file in text_files:
        futures.append(
            loop.run_in_executor(
                thread_pool,
                extract_predicates_from_text_ollama,
                text_file.stem,
                text_file,
            )
        )
        futures.append(
            loop.run_in_executor(
                process_pool,
                extract_predicates_from_text_regex,
                text_file.stem,
                text_file,
            )
        )

    results = await asyncio.gather(*futures)
    return results


def sync_tasks(device_ids: list[str]):
    import asyncio

    return asyncio.run(run_extract_tasks(device_ids))


def fda_extraction_pipeline(
    device_json_url: str = FDA_JSON_URL,
    pdf_dir: Path = DEFAULT_PDF_DIR,
    data_dir: Path = DEFAULT_DATA_DIR,
    USE_LLM_OCR: bool = False,
):
    # 1. Download and identify new devices
    print("Downloading device registry...")
    fda_data = download_device_json(device_json_url)
    new_devices = identify_new_devices(fda_data)
    print("Found", len(new_devices), "new devices to process")

    if not new_devices:
        print("No new devices to process. Exiting.")
        return

    from download import download_pdfs

    summary = download_pdfs(new_devices, pdf_dir)
    print(summary)

    # 2. Text Extraction
    from textify import extract_text_from_pdfs
    from textify_tesseract import extract_text_from_pdfs

    textify_device_ids = [p.stem for p in pdf_dir.glob("*.pdf")]
    text_results = extract_text_from_pdfs(textify_device_ids)
    tesseract_device_ids = [p.stem for p in pdf_dir.glob("*.pdf")]
    tesseract_results = extract_text_from_pdfs(tesseract_device_ids)

    # 3. Predicate Extraction
    from extract import (
        extract_predicates_from_text_regex,
        extract_predicates_from_text_ollama,
    )

    # - raw+regex
    # - tess+regex
    # - mistral+regex

    return
    # 2. Download PDFs concurrently
    print(f"Downloading PDFs (max {MAX_DOWNLOAD_WORKERS} concurrent)...")
    pdf_futures = [download_pdf.submit(device, pdf_dir) for device in new_devices]

    # 3. Process each device as its PDF becomes available
    print("Extracting text from PDFs...")
    extraction_futures = []

    for device, pdf_future in zip(new_devices, pdf_futures):
        pdf_path = pdf_future.result()  # Wait for this specific download
        text = extract_pdf_text(pdf_path)
        result_future = run_extraction_pipeline.submit(pdf_path, text, device)
        extraction_futures.append(result_future)

    # Collect all extraction results
    extraction_results = [f.result() for f in extraction_futures]

    # 4. Group by extraction type and report
    grouped = group_by_extraction_type(extraction_results)

    print("Extraction summary:")
    for ext_type, results in grouped.items():
        print(f"  {ext_type}: {len(results)} extractions")

    # 5. Merge with previous results
    print("Merging with previous results...")
    previous = load_previous_results(previous_results_path)
    merged = merge_results(previous, grouped)

    # Save merged results for next run
    with open(previous_results_path, "w") as f:
        json.dump(merged, f, indent=2)

    # Update processed IDs
    save_processed_ids(existing_ids, new_devices, existing_devices_path)

    # 6. Generate final dataset
    print("Generating final dataset...")
    final_path = generate_final_dataset(merged, output_path)

    print(f"Pipeline complete. Output: {final_path}")
    return final_path


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    fda_extraction_pipeline()
