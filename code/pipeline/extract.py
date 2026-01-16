import json
import pathlib
import re
from typing import Annotated, Callable

import requests
from pydantic import BaseModel, AfterValidator, SkipValidation

from lib import (
    DATA_PATH,
    PREDICATES_PATH,
)

# Case insensitive regex for K-numbers
K_NUMBER_PATTERN = re.compile(r"((k|den)\d{6})", re.IGNORECASE)
MALFORMED_PATTERN = re.compile(
    r"k\s*\d[\s\d]{5,8}", re.IGNORECASE
)  # K with spaces in digits


def validate_predicates(v: list[str]) -> list[str]:
    for predicate in v:
        if not re.match(r"(K|P|DEN)\d{6}", predicate):
            raise ValueError(f"Invalid predicate: {predicate}")
    return v


class ExtractionResult(BaseModel):
    """Complete extraction result for a single device."""

    device_id: str
    predicates: Annotated[list[str], AfterValidator(validate_predicates)]
    method: str  # "regex" or "ollama"
    source: str  # "raw", "tesseract", or "ministral"
    error: str | None = None
    type: str | None = None


def extract_k_numbers(text: str) -> list[str]:
    """Find all unique K-numbers."""
    matches = K_NUMBER_PATTERN.findall(text)
    matches = [m[0] for m in matches]
    return list(set(matches))


def extract_predicates_from_text_ollama(
    device_id: str,
    text_path: pathlib.Path,
    source: str = "raw",
    model: str = "ministral-3:3b",
) -> ExtractionResult | None:
    method = model
    folder = pathlib.Path(PREDICATES_PATH) / model / source
    folder.mkdir(parents=True, exist_ok=True)
    output_path = folder / f"{device_id}.json"

    if output_path.exists():
        with open(output_path, "r") as f:
            data = json.load(f)
        return ExtractionResult(**data)
    if device_id.startswith("DEN") or not text_path.exists():
        return ExtractionResult(
            device_id=device_id,
            predicates=[],
            method=method,
            source=source,
            error="Device ID starts with DEN or text file does not exist",
            type=f"ollama_{model}_{source}",
        )
    text = text_path.read_text()
    payload = {
        "model": "ministral-3:3b",
        "prompt": f"""
Identify the predicate device ids for these device submissions. Predicates are ONLY identified by device_ids like that look like K followed by 6 digits or DEN followed by 6 digits.
Not all device submissions have predicates. If so, return an empty list. Only return the predicate device ids, and not any text describing the device itself.
```text
{text}
```""",
        "stream": False,
        "options": {"temperature": 0.0},
        "format": {
            "type": "object",
            "properties": {
                "predicates": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                },
            },
        },
    }
    # take the stem of the text path parent folder
    try:
        response = requests.post(
            f"http://localhost:11434/api/generate", json=payload, timeout=120
        )
        data = json.loads(response.json()["response"])
        response.raise_for_status()
        extr = ExtractionResult(
            device_id=device_id,
            predicates=data.get("predicates", []),
            method=method,
            source=source,
            type=f"ollama_{model}_{source}",
        )
        with open(output_path, "w") as f:
            json.dump(extr.model_dump(), f, indent=2)
        return extr
    except Exception as e:
        return ExtractionResult(
            device_id=device_id,
            predicates=[],
            method=method,
            source=source,
            error=str(e),
            type=f"ollama_{model}_{source}",
        )


def extract_predicates_from_text_regex(
    device_id: str, text_path: pathlib.Path, source: str
) -> ExtractionResult | None:
    try:
        if device_id.startswith("DEN") or not text_path.exists():
            return ExtractionResult(
                device_id=device_id,
                predicates=[],
                method="regex",
                source=source,
                error="Device ID starts with DEN or text file does not exist",
                type=f"regex_{source}",
            )

        text = text_path.read_text()
        predicates = extract_k_numbers(text)
        predicates = [k.upper() for k in predicates]
        predicates = [k for k in predicates if k != device_id]

        return ExtractionResult(
            device_id=device_id,
            predicates=predicates,
            method="regex",
            source=source,
            type=f"regex_{source}",
        )
    except Exception as e:
        return ExtractionResult(
            device_id=device_id,
            predicates=[],
            method="regex",
            source=source,
            error=str(e),
            type=f"regex_{source}",
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

# Type alias for predicate extractor functions
PredicateExtractorFunc = Callable[[str, pathlib.Path, str], ExtractionResult | None]


class PredicateExtractorConfig(BaseModel):
    """Configuration for a predicate extraction method."""

    name: str
    func: SkipValidation[PredicateExtractorFunc]
    executor_type: str  # "process" or "thread"
    max_workers: int


PREDICATE_EXTRACTORS: dict[str, PredicateExtractorConfig] = {
    "regex": PredicateExtractorConfig(
        name="Extract Predicates (Regex)",
        func=extract_predicates_from_text_regex,
        executor_type="process",
        max_workers=4,
    ),
    "ollama": PredicateExtractorConfig(
        name="Extract Predicates (Ollama)",
        func=extract_predicates_from_text_ollama,
        executor_type="thread",
        max_workers=4,
    ),
}
