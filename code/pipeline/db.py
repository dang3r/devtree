"""
Device database management for tracking processing state.

Replaces predicates.json and suspicious.json with a unified db.json structure
that tracks predicates, verification status, errors, and extraction metadata.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class DeviceErrors(BaseModel):
    """Tracked errors for a device."""

    download_error: str | None = None
    extraction_error: str | None = None
    ocr_error: str | None = None


class TextExtraction:
    """Text extraction metadata."""

    extraction_method: Literal["pymupdf", "ocr", "none"]
    processing_time_ms: float
    processed_datetime: float

    text_length: int
    page_count: int


class DeviceEntry(BaseModel):
    """Single device entry in db.json."""

    predicates: list[str] = Field(default_factory=list)
    pdf_present: bool = False
    errors: DeviceErrors = Field(default_factory=DeviceErrors)

    # Extraction metadata
    text_extraction: TextExtraction = Field(default_factory=TextExtraction)


class DeviceDatabase(BaseModel):
    """Root structure for db.json."""

    schema_version: str = "1.0"
    last_updated: str = ""
    total_devices: int = 0
    total_predicate_references: int = 0
    devices: dict[str, DeviceEntry] = Field(default_factory=dict)


def load_db(path: Path) -> DeviceDatabase:
    """Load db.json or create empty database."""
    if not path.exists():
        return DeviceDatabase(last_updated=datetime.now(timezone.utc).isoformat())

    with open(path) as f:
        data = json.load(f)
    return DeviceDatabase.model_validate(data)


def save_db(db: DeviceDatabase, path: Path) -> None:
    """Save database with updated stats."""
    # Compute summary stats
    db.total_devices = len(db.devices)
    db.with_predicates = sum(1 for d in db.devices.values() if d.predicates)
    db.without_predicates = db.total_devices - db.with_predicates
    db.pdf_present_count = sum(1 for d in db.devices.values() if d.pdf_present)
    db.human_verified_count = sum(1 for d in db.devices.values() if d.human_verified)
    db.total_predicate_references = sum(len(d.predicates) for d in db.devices.values())
    db.last_updated = datetime.now(timezone.utc).isoformat()

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        json.dump(db.model_dump(), f, indent=2)


def get_devices_needing_processing(
    db: DeviceDatabase,
    fda_k_numbers: set[str],
    reprocess_months: int = 2,
) -> tuple[list[str], list[str]]:
    """
    Determine which devices need processing.

    Returns:
        (new_devices, reprocess_devices)
    """
    existing = set(db.devices.keys())
    new_devices = sorted(fda_k_numbers - existing)

    # Find devices from last N months that need re-processing
    cutoff = datetime.now(timezone.utc) - timedelta(days=reprocess_months * 30)
    reprocess = []

    for k_num, entry in db.devices.items():
        if not entry.pdf_present:
            continue
        if entry.human_verified:
            continue  # Don't re-process verified entries

        # Check if it was processed with pymupdf and has sparse text
        if entry.extraction_method == "pymupdf" and entry.chars_per_page < 50:
            # Only reprocess if recently processed
            if entry.last_processed:
                try:
                    processed_date = datetime.fromisoformat(entry.last_processed)
                    if processed_date > cutoff:
                        reprocess.append(k_num)
                except ValueError:
                    pass  # Invalid date format, skip

    return new_devices, sorted(reprocess)


def update_device_from_download(
    db: DeviceDatabase,
    k_number: str,
    success: bool,
    error: str | None = None,
) -> None:
    """Update device entry after download attempt."""
    if k_number not in db.devices:
        db.devices[k_number] = DeviceEntry()

    entry = db.devices[k_number]
    entry.pdf_present = success
    if error:
        entry.errors.download_error = error


def update_device_from_extraction(
    db: DeviceDatabase,
    k_number: str,
    predicates: list[str],
    extraction_method: Literal["pymupdf", "ocr", "none"],
    text_length: int,
    chars_per_page: float,
    page_count: int,
    flags: list[str],
    extraction_error: str | None = None,
    ocr_error: str | None = None,
) -> None:
    """Update device entry after extraction."""
    if k_number not in db.devices:
        db.devices[k_number] = DeviceEntry()

    entry = db.devices[k_number]
    entry.predicates = predicates
    entry.extraction_method = extraction_method
    entry.text_length = text_length
    entry.chars_per_page = chars_per_page
    entry.page_count = page_count
    entry.flags = flags
    entry.last_processed = datetime.now(timezone.utc).isoformat()

    if extraction_error:
        entry.errors.extraction_error = extraction_error
    if ocr_error:
        entry.errors.ocr_error = ocr_error


def set_human_verified(
    db: DeviceDatabase,
    k_number: str,
    predicates: list[str] | None = None,
) -> bool:
    """Mark a device as human verified, optionally updating predicates."""
    if k_number not in db.devices:
        return False

    entry = db.devices[k_number]
    if predicates is not None:
        entry.predicates = predicates
    entry.human_verified = True
    return True
