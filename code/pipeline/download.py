"""
Async PDF downloader for FDA 510(k) summary documents.

Downloads PDFs from FDA's CDRH database for specified K-numbers.
URL pattern: https://www.accessdata.fda.gov/cdrh_docs/pdf{YY}/{K_NUMBER}.pdf
"""

import asyncio
from datetime import datetime, timezone, timedelta
import io
import json
from pathlib import Path
import re
from typing import Literal
import zipfile
import datetime
from datetime import timezone

import httpx
from pydantic import BaseModel
import requests

from lib import PDF_DATA_PATH

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.38"}
MAX_CONCURRENT = 3
TIMEOUT = 30.0
SLEEP_TIME = 1.0

FDA_JSON_URL = (
    "https://download.open.fda.gov/device/510k/device-510k-0001-of-0001.json.zip"
)


class DownloadResult(BaseModel):
    """Result of a single PDF download."""

    device_id: str
    status: Literal["success", "failed", "skipped", "not_found"]
    file_path: str | None = None
    file_size: int | None = None
    error: str | None = None


class DownloadSummary(BaseModel):
    """Summary of all downloads."""

    total: int
    success: int
    failed: int
    skipped: int
    results: list[DownloadResult]


def db_url(device_id: str) -> str:
    return f"https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfPMN/pmn.cfm?ID={device_id}"


def build_pdf_url(device_id: str) -> str:
    """Build FDA PDF URL from K-number."""
    if device_id.startswith("DEN"):
        return f"https://www.accessdata.fda.gov/cdrh_docs/reviews/{device_id}.pdf"

    # Devices between 1976 and 2002 use the old format
    year_prefix = int(device_id[1:3])
    if year_prefix < 2 or year_prefix > 76:
        return f"https://www.accessdata.fda.gov/cdrh_docs/pdf/{device_id}.pdf"

    return f"https://www.accessdata.fda.gov/cdrh_docs/pdf{year_prefix}/{device_id}.pdf"


def download_pdf_sync(device_id: str, output_dir: Path) -> DownloadResult:
    """Synchronous download of a single PDF. For use with ThreadPoolExecutor."""
    import time

    output_path = output_dir / f"{device_id}.pdf"

    if output_path.exists():
        return DownloadResult(
            device_id=device_id,
            status="success",
            file_path=str(output_path),
            file_size=output_path.stat().st_size,
        )

    good_url = build_pdf_url(device_id)
    fb_url = f"https://www.accessdata.fda.gov/cdrh_docs/reviews/{device_id}.pdf"

    with httpx.Client(headers=HEADERS, timeout=TIMEOUT) as client:
        # Try primary URL
        try:
            headers = {**HEADERS, "User-Agent": HEADERS["User-Agent"] + device_id}
            response = client.get(good_url, follow_redirects=True, headers=headers)
            response.raise_for_status()
            output_path.write_bytes(response.content)
            return DownloadResult(
                device_id=device_id,
                status="success",
                file_path=str(output_path),
                file_size=len(response.content),
            )
        except httpx.HTTPStatusError:
            time.sleep(SLEEP_TIME)

        # Try fallback URL
        try:
            response = client.get(fb_url, follow_redirects=True, headers=headers)
            response.raise_for_status()
            output_path.write_bytes(response.content)
            return DownloadResult(
                device_id=device_id,
                status="success",
                file_path=str(output_path),
                file_size=len(response.content),
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return DownloadResult(
                    device_id=device_id,
                    status="not_found",
                    error=f"HTTP 404",
                )
            return DownloadResult(
                device_id=device_id,
                status="failed",
                error=f"HTTP {e.response.status_code}",
            )
        except httpx.RequestError as e:
            return DownloadResult(
                device_id=device_id,
                status="failed",
                error=str(e),
            )


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

    threshold_date = datetime.datetime.now(timezone.utc) - timedelta(days=365)
    device_date = datetime.datetime.strptime(
        device["decision_date"], "%Y-%m-%d"
    ).replace(tzinfo=timezone.utc)
    return device_date <= threshold_date


def is_recent_device(device: dict) -> bool:
    threshold_date = datetime.datetime.now(timezone.utc) - timedelta(days=30)
    device_date = datetime.datetime.strptime(
        device["decision_date"], "%Y-%m-%d"
    ).replace(tzinfo=timezone.utc)
    return device_date >= threshold_date


def pdf_data() -> dict:
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
