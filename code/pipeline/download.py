"""
Async PDF downloader for FDA 510(k) summary documents.

Downloads PDFs from FDA's CDRH database for specified K-numbers.
URL pattern: https://www.accessdata.fda.gov/cdrh_docs/pdf{YY}/{K_NUMBER}.pdf
"""

import asyncio
from datetime import datetime, timezone
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


async def _download_pdf(
    client: httpx.AsyncClient, url: str, output_path: Path, device_id: str
) -> DownloadResult:
    try:
        headers = {**HEADERS}
        headers["User-Agent"] = headers["User-Agent"] + device_id
        response = await client.get(url, follow_redirects=True, headers=headers)
        response.raise_for_status()
        output_path.write_bytes(response.content)
        return DownloadResult(
            device_id=device_id,
            status="success",
            file_path=str(output_path),
            file_size=len(response.content),
        )
    except httpx.HTTPStatusError as e:
        # if 404, return not_found
        if e.response.status_code == 404:
            return DownloadResult(
                device_id=device_id,
                status="not_found",
                error=f"HTTP {e.response.status_code}",
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


async def download_single_pdf(
    client: httpx.AsyncClient,
    device_id: str,
    output_dir: Path,
    semaphore: asyncio.Semaphore,
) -> DownloadResult:
    print(f"Downloading {device_id}...")
    output_path = output_dir / f"{device_id}.pdf"

    if output_path.exists():
        print(f"Skipping {device_id} because it already exists")
        return DownloadResult(
            device_id=device_id,
            status="skipped",
            file_path=str(output_path),
            file_size=output_path.stat().st_size,
        )

    # NOTE: The FDA db URL has a link to the summary and can be used to find the PDF URL.
    # This will always cause us to to do at least two requests.
    # Instead, try expected url and then review url. For most devices, only 1 request is needed.
    good_url = build_pdf_url(device_id)
    fb_url = f"https://www.accessdata.fda.gov/cdrh_docs/reviews/{device_id}.pdf"

    async with semaphore:
        good_res = await _download_pdf(client, good_url, output_path, device_id)
        await asyncio.sleep(SLEEP_TIME)
        if good_res.status == "success":
            print(f"Downloaded {device_id} from good URL")
            return good_res
        fb_res = await _download_pdf(client, fb_url, output_path, device_id)
        await asyncio.sleep(SLEEP_TIME)
        if fb_res.status == "success":
            print(f"Downloaded {device_id} from FB URL")
            return fb_res

        print(f"Failed to download {device_id}", good_res)
        return good_res


async def download_pdfs_async(
    device_ids: list[str],
    output_dir: Path,
    max_concurrent: int = MAX_CONCURRENT,
) -> DownloadSummary:
    """Download PDFs for all specified K-numbers."""
    output_dir.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(max_concurrent)

    print(f"Downloading {len(device_ids)} PDFs (max {max_concurrent} concurrent)...")
    async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT) as client:
        results = []
        tasks = [
            download_single_pdf(client, k_num, output_dir, semaphore)
            for k_num in device_ids
        ]
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
        return DownloadSummary(
            total=len(device_ids),
            success=sum(1 for r in results if r.status == "success"),
            failed=sum(1 for r in results if r.status == "failed"),
            skipped=sum(1 for r in results if r.status == "skipped"),
            results=results,
        )


def download_pdfs(
    k_numbers: list[str],
    output_dir: Path,
    max_concurrent: int = MAX_CONCURRENT,
) -> DownloadSummary:
    """Synchronous wrapper for PDF downloads."""
    return asyncio.run(download_pdfs_async(k_numbers, output_dir, max_concurrent))


def device_ids_without_pdfs(pdf_path: Path, fda_json_path: Path) -> list[str]:
    """Get device IDs without PDFs."""
    with open(fda_json_path) as f:
        fda_data = json.load(f)

    device_ids = [d["k_number"] for d in fda_data["results"]]
    return [d for d in device_ids if not (pdf_path / f"{d}.pdf").exists()]


def main():
    """Script for downloading PDFs for medical devices.

    Identify devices without local PDFs and download them. Only download devices
    that we no do not have a summary (be a good citizen and don't overwhelm the FDA).
    """

    fda_data = json.load(open(FDA_JSON_PATH))
    fda_device_ids = [d["k_number"] for d in fda_data["results"]]

    pdf_data = json.load(open(PDF_DATA_PATH))
    skip_device_ids = pdf_data["no_summary"]

    existing_pdfs = [p.stem for p in Path("pdfs").glob("*.pdf")]

    to_download = set(fda_device_ids) - set(skip_device_ids) - set(existing_pdfs)

    # filter for devices starting with K12
    to_download = [did for did in to_download if did.startswith("K90")]

    print("Found", len(to_download), "devices to download")

    # Only use 10 devices
    print("Attempting download of", len(to_download), "devices")
    input("Press Enter to continue...")

    summary = download_pdfs(
        [did for did in to_download],
        Path(__file__).parent.parent.parent / "pdfs",
    )

    # Save results
    for result in summary.results:
        if result.status == "not_found":
            pdf_data["no_summary"].append(result.device_id)
    with open(PDF_DATA_PATH, "w") as f:
        pdf_data["no_summary"].sort()
        json.dump(pdf_data, f, indent=2, default=str)


if __name__ == "__main__":
    main()
