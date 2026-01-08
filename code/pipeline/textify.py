from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from typing import List, Literal, Tuple
from lib import PDF_PATH, DeviceEntry, get_db, save_db, TEXT_PATH
from pathlib import Path
import fitz
from pydantic import BaseModel
import tqdm


class TextifyResult(BaseModel):
    device_id: str
    pdf_chars: int
    pdf_pages: int
    pdf_char_density: float
    pdf_label: str
    text_method: Literal["pymupdf", None] = None
    error: str | None = None


def extract_text_from_pdf(pdf_path: Path) -> Tuple[str, int]:
    with open(pdf_path, "rb") as f:
        pdf = fitz.open(f)

    text = ""
    for page in pdf:
        text += page.get_text()
    return text, pdf.page_count


def extract_text(device_id: str, device: DeviceEntry):
    try:
        if not device.has_pdf:
            return TextifyResult(
                pdf_chars=0,
                pdf_pages=0,
                pdf_char_density=0.0,
                pdf_label="",
                error="No PDF",
            )

        pdf_path = PDF_PATH / f"{device_id}.pdf"
        if not pdf_path.exists():
            return TextifyResult(
                pdf_chars=0,
                pdf_pages=0,
                pdf_char_density=0.0,
                pdf_label="",
                text_method="",
                error="No PDF",
            )
        # If we extracted text a different way, don't modify
        dst_path = TEXT_PATH / f"{device_id}.json"
        if dst_path.exists():
            with open(dst_path, "r") as f:
                text_data = json.load(f)
            if text_data["method"] != "pymupdf":
                return None

        text, pdf_pages = extract_text_from_pdf(pdf_path)
        pdf_chars = len(text)
        pdf_char_density = pdf_chars / pdf_pages
        pdf_label = "rich" if pdf_char_density > 100 else "sparse"

        # save the text and method to the text path as json
        text_data = {
            "text": text,
            "method": "pymupdf",
        }
        with open(dst_path, "w") as f:
            f.write(json.dumps(text_data, indent=2))
        return TextifyResult(
            device_id=device_id,
            pdf_chars=pdf_chars,
            pdf_pages=pdf_pages,
            pdf_char_density=pdf_char_density,
            pdf_label=pdf_label,
            text_method="pymupdf",
        )
    except Exception as e:
        return TextifyResult(
            device_id=device_id,
            pdf_chars=0,
            pdf_pages=0,
            pdf_char_density=0.0,
            pdf_label="",
            error=str(e),
        )


def extract_text_from_pdfs(device_entries: List[Tuple[str, DeviceEntry]]):
    with ProcessPoolExecutor() as executor:
        futures = [
            executor.submit(extract_text, device_id, device)
            for device_id, device in device_entries
        ]
        # use tqdm to show progress
        return [
            future.result()
            for future in tqdm.tqdm(as_completed(futures), total=len(futures))
        ]


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
