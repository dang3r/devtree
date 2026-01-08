#!/usr/bin/env python3
"""OCR a PDF using Ollama's vision model."""

import argparse
import base64
import io
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
    response.raise_for_status()
    data = response.json()
    return data.get("response", "")


def ocr_pdf(
    pdf_path: Path,
    output_path: Path,
    model: str = "gemma3",
    dpi: int = 100,
) -> str:
    """OCR all pages of a PDF with parallel processing."""
    if output_path.exists():
        print(f"Skipping {pdf_path.name} because {output_path} already exists")
        return pdf_path, output_path
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
    return pdf_path, output_path


def main():
    parser = argparse.ArgumentParser(description="OCR a PDF using Ollama")
    parser.add_argument("pdf_path", type=Path, help="Path to PDF directory")
    parser.add_argument("-o", "--output", type=Path, help="Output text directory")
    parser.add_argument(
        "-m", "--model", default="gemma3:1b", help="Ollama model to use"
    )
    parser.add_argument("--dpi", type=int, default=100, help="DPI for rendering pages")
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=16,
        help="Max concurrent pdf (default: 16)",
    )

    args = parser.parse_args()

    if not args.pdf_path.exists():
        print(f"Error: {args.pdf_path} not found")
        sys.exit(1)

    pdf_path = pathlib.Path(args.pdf_path)
    pdf_files = list(pdf_path.glob("**/*.pdf"))

    with ProcessPoolExecutor(max_workers=args.max_concurrent) as executor:
        futures = {
            executor.submit(
                ocr_pdf,
                pdf_file,
                args.output / (pdf_file.name + ".txt"),
                args.model,
                args.dpi,
            ): pdf_file
            for pdf_file in pdf_files
        }
        for future in tqdm(
            as_completed(futures), total=len(futures), desc="OCRing PDFs"
        ):
            try:
                pdf_path, output_path = future.result()
                tqdm.write(f"OCRed {pdf_path.name} to {output_path}")
            except Exception as e:
                traceback.print_exc()


if __name__ == "__main__":
    main()
