#!/usr/bin/env python3
"""OCR a PDF using Ollama's vision model."""

import base64
import io
import re
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import fitz  # pymupdf
import requests
from PIL import Image
from pydantic import BaseModel
from tqdm import tqdm

from lib import PDF_PATH, TEXT_PATH, get_db, save_db


class OcrOllamaResult(BaseModel):
    device_id: str
    output_path: Path
    method: str
    error: str | None = None


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


def ocr_pdf(
    device_id: str,
    model: str = "gemma3",
    dpi: int = 100,
) -> OcrOllamaResult:
    """OCR all pages of a PDF with parallel processing."""
    pdf_path = PDF_PATH / f"{device_id}.pdf"
    output_path = TEXT_PATH / f"{device_id}.txt"
    method = f"ollama_{model}_{dpi}"

    try:
        tqdm.write(f"OCRing {pdf_path.name} to {output_path}")
        doc = fitz.open(pdf_path)
        num_pages = len(doc)
        all_text = ""
        for page_num in range(num_pages):
            image_b64 = pdf_page_to_base64(pdf_path, page_num, dpi)
            text = ocr_image_with_ollama([image_b64], model)
            all_text += text

        # Save as plain .txt file
        output_path.write_text(all_text)
        doc.close()
        tqdm.write(f"OCRed {pdf_path.name} to {output_path}")
        return OcrOllamaResult(
            device_id=device_id,
            output_path=output_path,
            method=method,
        )
    except Exception as e:
        return OcrOllamaResult(
            device_id=device_id,
            output_path=output_path,
            method=method,
            error=str(e),
        )


def main():
    dpi = 100
    model = "ministral-3:3b"
    max_concurrent = 1

    db = get_db()

    # Find devices with PDFs that mention "predicate" but have no predicates extracted
    device_ids_to_ocr = []
    for device_id, entry in db.devices.items():
        if not entry.preds.values and entry.pdf.exists and device_id.startswith("K99"):
            txt_path = TEXT_PATH / f"{device_id}.txt"
            if not txt_path.exists():
                continue
            text = txt_path.read_text()
            predicates = re.findall("predicate", text, re.IGNORECASE)
            if len(predicates) > 1:
                device_ids_to_ocr.append(device_id)

    print(f"Found {len(device_ids_to_ocr)} devices to OCR")
    input("Press Enter to continue")

    with ProcessPoolExecutor(max_workers=max_concurrent) as executor:
        futures = {
            executor.submit(ocr_pdf, device_id, model, dpi): device_id
            for device_id in device_ids_to_ocr
        }
        for future in tqdm(
            as_completed(futures), total=len(futures), desc="OCRing PDFs"
        ):
            try:
                result = future.result()
                if result.error:
                    tqdm.write(f"Error OCRing {result.device_id}: {result.error}")
                else:
                    # Update DB with extraction method
                    entry = db.devices[result.device_id]
                    entry.text.extracted = True
                    entry.text.method = result.method
                    tqdm.write(f"OCRed {result.device_id} to {result.output_path}")
            except Exception:
                traceback.print_exc()

    save_db(db)


if __name__ == "__main__":
    main()
