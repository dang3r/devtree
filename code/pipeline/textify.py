from concurrent.futures import ProcessPoolExecutor, as_completed
import json
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


def extract_text(device_id: str) -> TextifyResult | None:
    try:
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
    device_ids: list[str],
) -> list[TextifyResult | None]:
    with ProcessPoolExecutor() as executor:
        futures = [executor.submit(extract_text, device_id) for device_id in device_ids]
        return [
            future.result()
            for future in tqdm.tqdm(as_completed(futures), total=len(futures))
        ]


def main():
    """Script for extracting text from PDFs.

    Extract text from PDFs for devices that we do not have text for and are not special cases(text extracted with a different method).
    """

    pdf_device_ids = [p.stem for p in PDF_PATH.glob("*.pdf")]
    special_cases = json.load(open("data/text.json"))["special_cases"]
    pdf_device_ids = set(pdf_device_ids) - set(special_cases)

    results = extract_text_from_pdfs(list(pdf_device_ids))
    for result in results:
        pass


if __name__ == "__main__":
    main()
