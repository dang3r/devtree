"""
Fetch FDA 510(k) JSON and diff for new devices.

Downloads the latest FDA device data and compares against the existing
data file or db.json to identify newly cleared devices and devices to reprocess.
"""

import json
import tempfile
import zipfile
from pathlib import Path

import httpx
from pydantic import BaseModel

from .db import DeviceDatabase, get_devices_needing_processing, load_db

FDA_510K_URL = "https://download.open.fda.gov/device/510k/device-510k-0001-of-0001.json.zip"
TIMEOUT = 120.0


class FetchResult(BaseModel):
    """Result of fetching and diffing FDA data."""

    new_k_numbers: list[str]
    reprocess_k_numbers: list[str] = []
    total_in_new: int
    total_in_existing: int
    new_count: int
    reprocess_count: int = 0


def download_fda_json(url: str = FDA_510K_URL) -> dict:
    """Download and extract FDA 510(k) JSON from zip file."""
    print(f"Downloading FDA data from {url}...")

    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()

    # Extract JSON from zip
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp.write(response.content)
        tmp_path = Path(tmp.name)

    try:
        with zipfile.ZipFile(tmp_path) as zf:
            # Find the JSON file in the zip
            json_files = [n for n in zf.namelist() if n.endswith(".json")]
            if not json_files:
                raise ValueError("No JSON file found in zip")

            with zf.open(json_files[0]) as f:
                data = json.load(f)
    finally:
        tmp_path.unlink()

    print(f"  Downloaded {len(data.get('results', [])):,} devices")
    return data


def extract_k_numbers(data: dict) -> set[str]:
    """Extract all K-numbers from FDA data."""
    k_numbers = set()
    for device in data.get("results", []):
        k_num = device.get("k_number", "")
        if k_num.startswith("K"):
            k_numbers.add(k_num)
    return k_numbers


def load_existing_data(path: Path) -> dict:
    """Load existing FDA data from file."""
    if not path.exists():
        return {"results": []}

    with open(path) as f:
        return json.load(f)


def fetch_and_diff(
    existing_path: Path,
    output_path: Path | None = None,
) -> tuple[FetchResult, dict]:
    """
    Fetch latest FDA data and diff against existing.

    Args:
        existing_path: Path to existing device-510k.json
        output_path: If provided, save new data here (defaults to existing_path)

    Returns:
        Tuple of (FetchResult with new K-numbers, full new data dict)
    """
    # Download new data
    new_data = download_fda_json()
    new_k_numbers = extract_k_numbers(new_data)

    # Load existing data
    existing_data = load_existing_data(existing_path)
    existing_k_numbers = extract_k_numbers(existing_data)

    # Find new devices
    added = new_k_numbers - existing_k_numbers
    added_list = sorted(added)

    print(f"  Existing devices: {len(existing_k_numbers):,}")
    print(f"  New devices: {len(new_k_numbers):,}")
    print(f"  Added: {len(added):,}")

    # Save new data if output path specified
    save_path = output_path or existing_path
    if added:
        print(f"  Saving updated data to {save_path}...")
        with open(save_path, "w") as f:
            json.dump(new_data, f)

    result = FetchResult(
        new_k_numbers=added_list,
        total_in_new=len(new_k_numbers),
        total_in_existing=len(existing_k_numbers),
        new_count=len(added),
    )

    return result, new_data


def get_devices_by_k_numbers(data: dict, k_numbers: set[str]) -> list[dict]:
    """Filter FDA data to only include specified K-numbers."""
    return [
        device
        for device in data.get("results", [])
        if device.get("k_number") in k_numbers
    ]


def fetch_and_diff_with_db(
    fda_json_path: Path,
    db_path: Path,
    reprocess_months: int = 2,
) -> tuple[FetchResult, dict, DeviceDatabase]:
    """
    Fetch FDA data and diff against db.json.

    Identifies new devices and devices that need reprocessing (sparse text,
    recently processed without OCR).

    Args:
        fda_json_path: Path to save/load FDA device JSON
        db_path: Path to db.json
        reprocess_months: How far back to look for reprocess candidates

    Returns:
        Tuple of (FetchResult, fda_data_dict, DeviceDatabase)
    """
    # Download new FDA data
    new_data = download_fda_json()
    new_k_numbers = extract_k_numbers(new_data)

    # Load database
    db = load_db(db_path)

    # Determine what to process
    new_devices, reprocess_devices = get_devices_needing_processing(
        db, new_k_numbers, reprocess_months
    )

    print(f"  DB devices: {len(db.devices):,}")
    print(f"  New devices: {len(new_devices):,}")
    print(f"  Reprocess candidates: {len(reprocess_devices):,}")

    # Save new FDA data
    if new_devices or not fda_json_path.exists():
        print(f"  Saving FDA data to {fda_json_path}...")
        fda_json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(fda_json_path, "w") as f:
            json.dump(new_data, f)

    result = FetchResult(
        new_k_numbers=new_devices,
        reprocess_k_numbers=reprocess_devices,
        total_in_new=len(new_k_numbers),
        total_in_existing=len(db.devices),
        new_count=len(new_devices),
        reprocess_count=len(reprocess_devices),
    )

    return result, new_data, db
