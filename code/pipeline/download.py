"""
Async PDF downloader for FDA 510(k) summary documents.

Downloads PDFs from FDA's CDRH database for specified K-numbers.
URL pattern: https://www.accessdata.fda.gov/cdrh_docs/pdf{YY}/{K_NUMBER}.pdf
"""

import asyncio
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import re
from typing import Literal

import httpx
from pydantic import BaseModel

from lib import FDA_JSON_PATH, PDF_DATA_PATH

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.38"}
MAX_CONCURRENT = 3
TIMEOUT = 30.0
SLEEP_TIME = 1.0


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
