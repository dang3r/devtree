from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from pathlib import Path
from typing import Literal

import fitz
import tqdm
from pydantic import BaseModel

from lib import PDF_PATH, TEXT_PATH, RAWTEXT_PATH

fitz.TOOLS.mupdf_display_errors(False)


class TextifyResult(BaseModel):
    device_id: str
    text_method: str
    error: str | None = None
    filepath: Path | None = None


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
                error="PDF file missing",
                text_method="pymupdf",
            )

        dst_path = RAWTEXT_PATH / f"{device_id}.txt"
        if dst_path.exists():
            return TextifyResult(
                device_id=device_id,
                text_method="pymupdf",
                filepath=dst_path,
            )

        text, pdf_pages = extract_text_from_pdf(pdf_path)
        dst_path.write_text(text)
        return TextifyResult(
            device_id=device_id,
            text_method="pymupdf",
            filepath=dst_path,
        )
    except Exception as e:
        return TextifyResult(
            device_id=device_id,
            error=str(e),
            text_method="pymupdf",
        )
