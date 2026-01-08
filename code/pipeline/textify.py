from concurrent.futures import ProcessPoolExecutor
from typing import List, Tuple
from lib import DeviceEntry, get_db, save_db
from pathlib import Path
import fitz
from pydantic import BaseModel


class TextifyResult(BaseModel):
    pdf_chars: int
    pdf_pages: int
    pdf_char_density: float
    pdf_label: str
    error: str | None = None


def extract_text_from_pdf(pdf_path: Path) -> str:
    with open(pdf_path, "rb") as f:
        pdf = fitz.open(f)

    text = ""
    for page in pdf:
        text += page.get_text()
    return pdf.text


def is_scanned_pdf(pdf: fitz.Document) -> bool:
    return len(pdf.text) / len(pdf) > 100


def extract_text(device_id: str, device: DeviceEntry):
    if not device.has_pdf:
        return None


def extract_text_from_pdfs(device_entries: List[Tuple[str, DeviceEntry]]):
    with ProcessPoolExecutor() as executor:
        futures = [
            executor.submit(extract_text, device_id, device)
            for device_id, device in device_entries
        ]
        results = [future.result() for future in futures]
    return results


def main():
    db = get_db()
    device_entries = [(device_id, device) for device_id, device in db.devices.items()]
    results = extract_text_from_pdfs(device_entries)
    for result in results:
        if result is not None:
            db.devices[result.device_id].pdf_chars = result.pdf_chars
            db.devices[result.device_id].pdf_pages = result.pdf_pages
            db.devices[result.device_id].pdf_char_density = result.pdf_char_density
            db.devices[result.device_id].pdf_label = result.pdf_label
    save_db(db)


if __name__ == "__main__":
    main()
