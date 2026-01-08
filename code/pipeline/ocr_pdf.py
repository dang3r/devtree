#!/usr/bin/env python3
"""OCR a PDF using Ollama's vision model."""

import argparse
import base64
import io
import json
import sys
import threading
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
import pathlib
import traceback
import fitz  # pymupdf
import requests
from PIL import Image
from tqdm import tqdm

from pydantic import BaseModel

from lib import PDF_PATH, get_db, save_db, TEXT_PATH


class OcrOllamaResult(BaseModel):
    device_id: str
    output_path: Path
    error: str | None = None
    model: str


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
) -> str:
    """OCR all pages of a PDF with parallel processing."""
    try:
        pdf_path = PDF_PATH / f"{device_id}.pdf"
        output_path = TEXT_PATH / f"{device_id}.json"

        # OCR
        tqdm.write(f"OCRing {pdf_path.name} to {output_path}")
        doc = fitz.open(pdf_path)
        num_pages = len(doc)
        all_text = ""
        for page_num in range(num_pages):
            image_b64 = pdf_page_to_base64(pdf_path, page_num, dpi)
            text = ocr_image_with_ollama([image_b64], model)
            all_text += text

        text_data = {
            "text": all_text,
            "method": f"ollama_{model}_{dpi}",
        }
        output_path.write_text(json.dumps(text_data, indent=2))
        doc.close()
        tqdm.write(f"OCRed {pdf_path.name} to {output_path}")
        return OcrOllamaResult(
            device_id=pdf_path.name,
            output_path=output_path,
            model=model,
        )
    except Exception as e:
        return OcrOllamaResult(
            device_id=device_id,
            output_path=output_path,
            error=str(e),
            model=model,
        )


def main():
    dpi = 100
    model = "ministral-3:3b"
    max_concurrent = 1
    output_path = TEXT_PATH

    db = get_db()
    device_ids_with_discrepancy = []
    for device_id, device in db.devices.items():
        if not device.predicates and device.has_pdf and device_id.startswith("K99"):
            fpath = TEXT_PATH / f"{device_id}.json"
            if not fpath.exists():
                continue
            text = json.load(open(TEXT_PATH / f"{device_id}.json"))["text"]
            import re

            predicates = re.findall("predicate", text, re.IGNORECASE)
            if len(predicates) > 1:
                device_ids_with_discrepancy.append(device_id)

    print(len(device_ids_with_discrepancy))

    print(f"OCRing {len(device_ids_with_discrepancy)} devices")
    input("Press Enter to continue")

    with ProcessPoolExecutor(max_workers=max_concurrent) as executor:
        futures = {
            executor.submit(
                ocr_pdf,
                device_id,
                model,
                dpi,
            ): device_id
            for device_id in device_ids_with_discrepancy
        }
        for future in tqdm(
            as_completed(futures), total=len(futures), desc="OCRing PDFs"
        ):
            try:
                result = future.result()
                tqdm.write(f"OCRed {result.device_id} to {result.output_path}")
            except Exception as e:
                traceback.print_exc()


if __name__ == "__main__":
    main()
