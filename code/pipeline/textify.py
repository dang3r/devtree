from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Literal

import fitz
import tqdm
from pydantic import BaseModel

from lib import PDF_PATH, TEXT_PATH, DeviceEntry, get_db, save_db


class TextifyResult(BaseModel):
    device_id: str
    pdf_chars: int
    pdf_pages: int
    pdf_char_density: float
    pdf_quality: str
    text_method: Literal["pymupdf"] | None = None
    error: str | None = None


def extract_text_from_pdf(pdf_path: Path) -> tuple[str, int]:
    with open(pdf_path, "rb") as f:
        pdf = fitz.open(f)

    text = ""
    for page in pdf:
        text += page.get_text()
    return text, pdf.page_count


def extract_text(device_id: str, device: DeviceEntry) -> TextifyResult | None:
    try:
        if not device.pdf.exists:
            return TextifyResult(
                device_id=device_id,
                pdf_chars=0,
                pdf_pages=0,
                pdf_char_density=0.0,
                pdf_quality="",
                error="No PDF",
            )

        pdf_path = PDF_PATH / f"{device_id}.pdf"
        if not pdf_path.exists():
            return TextifyResult(
                device_id=device_id,
                pdf_chars=0,
                pdf_pages=0,
                pdf_char_density=0.0,
                pdf_quality="",
                error="PDF file missing",
            )

        # Skip if already extracted with a non-pymupdf method
        if device.text.extracted and device.text.method != "pymupdf":
            return None

        text, pdf_pages = extract_text_from_pdf(pdf_path)
        pdf_chars = len(text)
        pdf_char_density = pdf_chars / pdf_pages if pdf_pages > 0 else 0.0
        pdf_quality = "rich" if pdf_char_density > 100 else "sparse"

        # Save as plain .txt file
        dst_path = TEXT_PATH / f"{device_id}.txt"
        dst_path.write_text(text)

        return TextifyResult(
            device_id=device_id,
            pdf_chars=pdf_chars,
            pdf_pages=pdf_pages,
            pdf_char_density=pdf_char_density,
            pdf_quality=pdf_quality,
            text_method="pymupdf",
        )
    except Exception as e:
        return TextifyResult(
            device_id=device_id,
            pdf_chars=0,
            pdf_pages=0,
            pdf_char_density=0.0,
            pdf_quality="",
            error=str(e),
        )


def extract_text_from_pdfs(
    device_entries: list[tuple[str, DeviceEntry]],
) -> list[TextifyResult | None]:
    with ProcessPoolExecutor() as executor:
        futures = [
            executor.submit(extract_text, device_id, device)
            for device_id, device in device_entries
        ]
        return [
            future.result()
            for future in tqdm.tqdm(as_completed(futures), total=len(futures))
        ]


def main():
    db = get_db()
    device_entries = [(device_id, device) for device_id, device in db.devices.items()]
    results = extract_text_from_pdfs(device_entries)

    for result in results:
        if result is None:
            continue
        entry = db.devices[result.device_id]
        entry.pdf.chars = result.pdf_chars
        entry.pdf.pages = result.pdf_pages
        entry.pdf.density = result.pdf_char_density
        entry.pdf.quality = result.pdf_quality
        if result.text_method:
            entry.text.extracted = True
            entry.text.method = result.text_method

    save_db(db)


if __name__ == "__main__":
    main()
