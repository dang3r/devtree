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
MAX_CONCURRENT = 10
SAMPLE_SIZE = 20
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

    def record_success(self, k_number: str, file_path: Path) -> None:
        existing = self.results.get(k_number)
        self.results[k_number] = DownloadResult(
            status="success",
            attempted_at=datetime.now(timezone.utc).isoformat(),
            file_path=str(file_path),
            retry_count=(existing.retry_count if existing else 0),
        )

    def record_failure(self, k_number: str, error: str) -> None:
        existing = self.results.get(k_number)
        self.results[k_number] = DownloadResult(
            status="failed",
            attempted_at=datetime.now(timezone.utc).isoformat(),
            error=error,
            retry_count=(existing.retry_count + 1 if existing else 1),
        )


def load_sample_devices(
    data_file: Path, sample_size: int, seed: int = 41
) -> list[Device]:
    """Load random sample of 510(k) devices from 2015-2025."""
    with open(data_file) as f:
        data = json.load(f)

    # Filter for 2015-2025, K-numbers only (exclude DEN, etc.)
    year_prefixes = (
        "2015",
        "2016",
        "2017",
        "2018",
        "2019",
        "2020",
        "2021",
        "2022",
        "2023",
        "2024",
        "2025",
    )
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
    manifest: Manifest,
    semaphore: asyncio.Semaphore,
) -> bool:
    """Download a 510(k) summary PDF. Returns True on success."""
    url = build_pdf_url(device.k_number)
    output_path = output_dir / f"{device.k_number}.pdf"

    # Skip if already successfully downloaded
    existing = manifest.results.get(device.k_number)
    if existing and existing.status == "success" and output_path.exists():
        print(f"  [skip] {device.k_number} - already downloaded")
        return True

    async with semaphore:
        print(f"  [GET]  {device.k_number}")

        try:
            response = await client.get(url, follow_redirects=True, timeout=30.0)
            response.raise_for_status()

            output_path.write_bytes(response.content)
            manifest.record_success(device.k_number, output_path)
            print(f"  [OK]   {device.k_number} - {len(response.content) / 1024:.1f} KB")
            return True

        except httpx.HTTPStatusError as e:
            error = f"HTTP {e.response.status_code}"
            manifest.record_failure(device.k_number, error)
            print(f"  [ERR]  {device.k_number} - {error}")
            return False
        except httpx.RequestError as e:
            error = str(e)
            manifest.record_failure(device.k_number, error)
            print(f"  [ERR]  {device.k_number} - {error}")
            return False


MANIFEST_PATH = Path("manifest.json")


async def download_all(
    devices: list[Device], output_dir: Path, manifest: Manifest
) -> int:
    """Download all PDFs concurrently. Returns success count."""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async with httpx.AsyncClient(headers=HEADERS) as client:
        tasks = [
            download_pdf(client, device, output_dir, manifest, semaphore)
            for device in devices
        ]
        results = await asyncio.gather(*tasks)

    return sum(results)


async def main() -> None:
    output_dir = Path("pdfs")
    output_dir.mkdir(exist_ok=True)

    devices = load_sample_devices(DATA_FILE, SAMPLE_SIZE)
    manifest = Manifest.load(MANIFEST_PATH)
    print(
        f"Downloading {len(devices)} PDFs to {output_dir}/ (max {MAX_CONCURRENT} concurrent)\n"
    )

    success_count = await download_all(devices, output_dir, manifest)
    manifest.save(MANIFEST_PATH)

    # Summary
    failed = [k for k, v in manifest.results.items() if v.status == "failed"]
    print(f"\nDownloaded {success_count}/{len(devices)} PDFs")
    if failed:
        print(f"Failed: {', '.join(failed)}")


if __name__ == "__main__":
    asyncio.run(main())
