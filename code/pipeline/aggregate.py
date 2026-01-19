"""
Predicate aggregation logic.

Combines extraction results from multiple methods and sources,
selecting the best result for each device based on priority.
"""

import json
import pathlib
from typing import Any

from extract import ExtractionResult

NEW_EXTRACTION_PRIORITY = {
    "human_raw": 0,
    "claude_code_raw": 1,
    "openrouter_pymupdf": 2,
    "openrouter_tesseract": 3,
    "ollama_ministral-3:3b_ministral": 2,
    "ollama_ministral-3:3b_pymupdf": 3,
    "ollama_ministral-3:3b_tesseract": 4,
    "regex_ministral3b": 6,
    "regex_pymupdf": 7,
    "regex_tesseract": 8,
}


# ---------------------------------------------------------------------------
# Aggregation Functions
# ---------------------------------------------------------------------------


def aggregate_predicates(extract_results: list[ExtractionResult]) -> dict[str, dict]:
    """
    Aggregate extraction results, selecting the best result per device.

    For each device, selects the extraction result with the lowest priority
    score (highest quality).
    """
    by_device: dict[str, list[tuple[int, ExtractionResult]]] = {}

    for extract_result in extract_results:
        if extract_result and not extract_result.error:
            key = extract_result.type
            priority = NEW_EXTRACTION_PRIORITY.get(key, 99)
            if extract_result.device_id not in by_device:
                by_device[extract_result.device_id] = []
            by_device[extract_result.device_id].append((priority, extract_result))

    aggregated = {}
    for device_id, entries in by_device.items():
        best = min(entries, key=lambda x: x[0])[1]
        aggregated[device_id] = {
            "predicates": best.predicates,
            "method": best.method,
            "source": best.source,
            "type": best.type,
        }

    # ensure dict keys are sorted by device_id
    aggregated = dict(sorted(aggregated.items(), key=lambda x: x[0]))
    return aggregated


def load_existing_predicates() -> list[ExtractionResult]:
    """
    Load existing predicate extractions from ground truth files.

    Returns a list of ExtractionResult objects from previously
    extracted/verified predicates.
    """
    # read from data/gt/predicates.json which has everything
    base = pathlib.Path(__file__).parent.parent.parent / "data" / "gt"
    filepath = base / "predicates.json"
    if not filepath.exists():
        raise FileNotFoundError(f"Predicates file not found at {filepath}")
    with open(filepath, "r") as f:
        data = json.load(f)
    extraction_results = []
    for key, value in data.items():
        extraction_results.append(
            ExtractionResult(
                device_id=key,
                predicates=value["predicates"],
                method=value["method"],
                source=value["source"],
                type=value["type"],
            )
        )
    return extraction_results
