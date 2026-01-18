"""
Text extraction from PDFs using multiple methods:
- PyMuPDF: Fast direct text extraction for digital PDFs
- Tesseract: OCR for scanned PDFs
- Ollama: LLM vision model OCR for complex layouts
"""

import base64
import io
from pathlib import Path
from typing import Callable

import fitz
import pytesseract
import requests
from PIL import Image
from pydantic import BaseModel, SkipValidation
from tqdm import tqdm

from lib import PDF_PATH, RAWTEXT_PATH, TESSERACT_TEXT_PATH, MINISTRAL3_3B_PATH

fitz.TOOLS.mupdf_display_errors(False)


class TextifyResult(BaseModel):
    device_id: str
    text_method: str
    error: str | None = None
    filepath: Path | None = None

    # make a type attribute function
    def type(self) -> str:
        if "pymupdf" in self.text_method:
            return "pymupdf"
        elif "tesseract" in self.text_method:
            return "tesseract"
        elif "ministral" in self.text_method:
            return "ministral"
        else:
            raise ValueError(f"Unknown text method: {self.text_method}")


# ---------------------------------------------------------------------------
# PyMuPDF Text Extraction
# ---------------------------------------------------------------------------


def extract_text_from_pdf(pdf_path: Path) -> tuple[str, int]:
    """Extract text directly from PDF using PyMuPDF."""
    with open(pdf_path, "rb") as f:
        pdf = fitz.open(f)

    text = ""
    for page in pdf:
        text += page.get_text()
    return text, pdf.page_count


def extract_text_pymupdf(device_id: str) -> TextifyResult:
    """Extract text from a device PDF using PyMuPDF."""
    try:
        pdf_path = PDF_PATH / f"{device_id}.pdf"
        if not pdf_path.exists():
            return TextifyResult(
                device_id=device_id,
                error="PDF file missing",
                text_method="pymupdf",
                type="pymupdf",
            )

        dst_path = RAWTEXT_PATH / f"{device_id}.txt"
        if dst_path.exists():
            return TextifyResult(
                device_id=device_id,
                text_method="pymupdf",
                filepath=dst_path,
                type="pymupdf",
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


# ---------------------------------------------------------------------------
# Tesseract OCR Text Extraction
# ---------------------------------------------------------------------------


def pdf_to_images(pdf_path: Path, dpi: int = 300) -> list[Image.Image]:
    """Convert PDF pages to PIL Images using PyMuPDF."""
    doc = fitz.open(pdf_path)
    images = []

    for page in doc:
        zoom = dpi / 72  # 72 is the default PDF DPI
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
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


def extract_text_tesseract(device_id: str) -> TextifyResult:
    """Extract text from a device PDF using Tesseract OCR."""
    method = "tesseract"
    try:
        pdf_path = PDF_PATH / f"{device_id}.pdf"
        text_path = TESSERACT_TEXT_PATH / f"{device_id}.txt"

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


# ---------------------------------------------------------------------------
# Ollama Vision Model OCR
# ---------------------------------------------------------------------------


def pdf_page_to_base64(pdf_path: Path, page_num: int, dpi: int = 100) -> str:
    """Convert a PDF page to base64 encoded PNG."""
    doc = fitz.open(pdf_path)
    page = doc[page_num]

    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    doc.close()
    return base64.b64encode(buffer.read()).decode("utf-8")


def ocr_image_with_ollama(
    images: list[str],
    model: str = "gemma3",
    ollama_url: str = "http://localhost:11434",
) -> str:
    """Send image to Ollama for OCR."""
    payload = {
        "model": model,
        "prompt": "Extract all text from these images. Return only the extracted text Do not include any other text in your response.",
        "images": images,
        "stream": False,
        "options": {"temperature": 0.0},
    }
    response = requests.post(f"{ollama_url}/api/generate", json=payload, timeout=120)
    data = response.json()
    return data.get("response", "")


def extract_text_ollama_ocr(
    device_id: str,
    model: str = "ministral-3:3b",
    dpi: int = 100,
) -> TextifyResult:
    """OCR all pages of a PDF using Ollama vision model."""
    pdf_path = PDF_PATH / f"{device_id}.pdf"
    output_path = MINISTRAL3_3B_PATH / f"{device_id}.txt"
    method = f"ollama_{model}_{dpi}"

    if output_path.exists():
        return TextifyResult(
            device_id=device_id,
            filepath=output_path,
            text_method=method,
        )

    try:
        tqdm.write(f"OCRing {pdf_path.name} to {output_path}")
        doc = fitz.open(pdf_path)
        num_pages = len(doc)
        all_text = ""
        for page_num in range(num_pages):
            image_b64 = pdf_page_to_base64(pdf_path, page_num, dpi)
            text = ocr_image_with_ollama([image_b64], model)
            all_text += text

        output_path.write_text(all_text)
        doc.close()
        tqdm.write(f"OCRed {pdf_path.name} to {output_path}")
        return TextifyResult(
            device_id=device_id,
            filepath=output_path,
            text_method=method,
        )
    except Exception as e:
        return TextifyResult(
            device_id=device_id,
            filepath=output_path,
            text_method=method,
            error=str(e),
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TextExtractorConfig(BaseModel):
    """Configuration for a text extraction method."""

    name: str
    func: SkipValidation[Callable[[str], TextifyResult]]
    executor_type: str  # "process" or "thread"
    max_workers: int


TEXT_EXTRACTORS: dict[str, TextExtractorConfig] = {
    "pymupdf": TextExtractorConfig(
        name="Extract Text (PyMuPDF)",
        func=extract_text_pymupdf,
        executor_type="process",
        max_workers=4,
    ),
    "tesseract": TextExtractorConfig(
        name="Extract Text (Tesseract)",
        func=extract_text_tesseract,
        executor_type="process",
        max_workers=4,
    ),
    "ollama": TextExtractorConfig(
        name="Extract Text (Ollama)",
        func=extract_text_ollama_ocr,
        executor_type="thread",
        max_workers=1,
    ),
}
