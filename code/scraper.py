"""
FDA 510(k) PDF Scraper

Downloads summary PDFs for 510(k) devices from FDA's CDRH database.
URL pattern: https://www.accessdata.fda.gov/cdrh_docs/pdf{YY}/{K_NUMBER}.pdf
"""

import asyncio
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel


HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
MAX_CONCURRENT = 3
SAMPLE_SIZE = 10
DATA_FILE = Path("device-510k-0001-of-0001.json")


class Device(BaseModel):
    k_number: str
    decision_date: str
    device_name: str


class DownloadResult(BaseModel):
    status: Literal["success", "failed"]
    attempted_at: str
    file_path: str | None = None
    error: str | None = None
    retry_count: int = 0


class Manifest(BaseModel):
    """Tracks download results for all devices."""

    results: dict[str, DownloadResult] = {}

    @classmethod
    def load(cls, path: Path) -> "Manifest":
        if path.exists():
            return cls.model_validate_json(path.read_text())
        return cls()

    def save(self, path: Path) -> None:
        path.write_text(self.model_dump_json(indent=2))


def load_sample_devices(
    data_file: Path, sample_size: int, seed: int = 40
) -> list[Device]:
    """Load random sample of 510(k) devices from 2015-2025."""
    with open(data_file) as f:
        data = json.load(f)

    # Filter for 2015-2025, K-numbers only (exclude DEN, etc.)
    year_prefixes = ("2010",)
    candidates = [
        r
        for r in data["results"]
        if r.get("decision_date", "").startswith(year_prefixes)
        and r.get("k_number", "").startswith("K")
    ]

    random.seed(seed)
    sampled = random.sample(candidates, min(sample_size, len(candidates)))

    return [
        Device(
            k_number=r["k_number"],
            decision_date=r["decision_date"],
            device_name=r["device_name"],
        )
        for r in sampled
    ]


def build_pdf_url(k_number: str) -> str:
    """Build the FDA PDF URL from a K-number.

    K-numbers follow pattern K{YY}{NNNN} where YY is the 2-digit year.
    PDFs are at: https://www.accessdata.fda.gov/cdrh_docs/pdf{YY}/{K_NUMBER}.pdf
    """
    # Extract year prefix (e.g., "K21" -> "21")
    year_prefix = k_number[1:3]
    return f"https://www.accessdata.fda.gov/cdrh_docs/pdf{year_prefix}/{k_number}.pdf"


async def download_pdf(
    client: httpx.AsyncClient,
    device: Device,
    output_dir: Path,
    existing_result: DownloadResult | None,
    semaphore: asyncio.Semaphore,
) -> tuple[str, DownloadResult]:
    """Download a 510(k) summary PDF. Returns (k_number, result)."""
    url = build_pdf_url(device.k_number)
    output_path = output_dir / f"{device.k_number}.pdf"
    retry_count = existing_result.retry_count if existing_result else 0

    # Skip if already successfully downloaded
    if existing_result and existing_result.status == "success" and output_path.exists():
        print(f"  [skip] {device.k_number} - already downloaded")
        return (device.k_number, existing_result)

    async with semaphore:
        print(f"  [GET]  {device.k_number}")

        try:
            response = await client.get(url, follow_redirects=True, timeout=30.0)
            response.raise_for_status()

            output_path.write_bytes(response.content)
            result = DownloadResult(
                status="success",
                attempted_at=datetime.now(timezone.utc).isoformat(),
                file_path=str(output_path),
                retry_count=retry_count,
            )
            print(f"  [OK]   {device.k_number} - {len(response.content) / 1024:.1f} KB")
            return (device.k_number, result)

        except httpx.HTTPStatusError as e:
            error = f"HTTP {e.response.status_code}"
            result = DownloadResult(
                status="failed",
                attempted_at=datetime.now(timezone.utc).isoformat(),
                error=error,
                retry_count=retry_count + 1,
            )
            print(f"  [ERR]  {device.k_number} - {error}")
            return (device.k_number, result)

        except httpx.RequestError as e:
            result = DownloadResult(
                status="failed",
                attempted_at=datetime.now(timezone.utc).isoformat(),
                error=str(e),
                retry_count=retry_count + 1,
            )
            print(f"  [ERR]  {device.k_number} - {e}")
            return (device.k_number, result)


MANIFEST_PATH = Path("manifest.json")


async def download_all(
    devices: list[Device], output_dir: Path, existing_manifest: Manifest
) -> Manifest:
    """Download all PDFs concurrently. Returns new manifest with results."""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async with httpx.AsyncClient(headers=HEADERS) as client:
        tasks = [
            download_pdf(
                client,
                device,
                output_dir,
                existing_manifest.results.get(device.k_number),
                semaphore,
            )
            for device in devices
        ]
        results = await asyncio.gather(*tasks)

    return Manifest(results=dict(results))


async def main() -> None:
    output_dir = Path("pdfs")
    output_dir.mkdir(exist_ok=True)

    devices = load_sample_devices(DATA_FILE, SAMPLE_SIZE)
    existing_manifest = Manifest.load(MANIFEST_PATH)
    print(
        f"Downloading {len(devices)} PDFs to {output_dir}/ (max {MAX_CONCURRENT} concurrent)\n"
    )

    manifest = await download_all(devices, output_dir, existing_manifest)
    manifest.save(MANIFEST_PATH)

    # Summary
    success_count = sum(1 for v in manifest.results.values() if v.status == "success")
    failed = [k for k, v in manifest.results.items() if v.status == "failed"]
    print(f"\nDownloaded {success_count}/{len(devices)} PDFs")
    if failed:
        print(f"Failed: {', '.join(failed)}")


if __name__ == "__main__":
    asyncio.run(main())
