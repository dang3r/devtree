from concurrent.futures import ProcessPoolExecutor, as_completed
import json
from pathlib import Path
from typing import Literal

import fitz
import pytesseract
import tqdm
from PIL import Image
from pydantic import BaseModel

from textify import TextifyResult
from lib import PDF_PATH, TESSERACT_TEXT_PATH


def pdf_to_images(pdf_path: Path, dpi: int = 300) -> list[Image.Image]:
    """Convert PDF pages to PIL Images using PyMuPDF."""
    doc = fitz.open(pdf_path)
    images = []

    for page in doc:
        # Create a matrix for the desired DPI
        zoom = dpi / 72  # 72 is the default PDF DPI
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        # Convert to PIL Image
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)

    doc.close()
    return images


def extract_text_from_pdf_tesseract(pdf_path: Path, dpi: int = 100) -> tuple[str, int]:
    """Extract text from PDF using Tesseract OCR."""
    images = pdf_to_images(pdf_path, dpi=dpi)

    text_parts = []
    for img in images:
        page_text = pytesseract.image_to_string(img)
        text_parts.append(page_text)

    full_text = "\n\n".join(text_parts)
    return full_text, len(images)


def extract_text(device_id: str) -> TextifyResult:
    """Extract text from a single device PDF using Tesseract."""
    try:
        pdf_path = PDF_PATH / f"{device_id}.pdf"
        text_path = TESSERACT_TEXT_PATH / f"{device_id}.txt"
        method = "tesseract"
        if not pdf_path.exists():
            return TextifyResult(
                device_id=device_id,
                error="PDF file missing",
                text_method=method,
            )

        if text_path.exists():
            return TextifyResult(
                device_id=device_id,
                text_method=method,
                filepath=text_path,
            )
        text, pdf_pages = extract_text_from_pdf_tesseract(pdf_path)
        text_path.write_text(text)

        return TextifyResult(
            device_id=device_id,
            text_method=method,
            filepath=text_path,
        )
    except Exception as e:
        return TextifyResult(
            device_id=device_id,
            error=str(e),
            text_method=method,
        )
