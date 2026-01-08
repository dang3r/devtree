import json
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Literal

import tqdm
from lib import DeviceEntry, TEXT_PATH

from pydantic import BaseModel

# make case insensitive regex
K_NUMBER_PATTERN = re.compile(r"((k|den)\d{6})", re.IGNORECASE)
MALFORMED_PATTERN = re.compile(
    r"k\s*\d[\s\d]{5,8}", re.IGNORECASE
)  # K with spaces in digits


class ExtractionResult(BaseModel):
    """Complete extraction result for a single device."""

    device_id: str
    predicates: list[str]
    malformed_predicates: list[str]
    error: str | None = None
    extraction_method: str


def extract_k_numbers(text: str) -> list[str]:
    """Find all unique K-numbers, preserving order."""
    # we now have 1 capture group for the k or den number but return full string for convenience
    matches = K_NUMBER_PATTERN.findall(text)
    matches = [m[0] for m in matches]
    return list(set(matches))


def find_malformed_k_numbers(text: str) -> list[str]:
    """Find K-numbers with spaces or typos."""
    matches = MALFORMED_PATTERN.findall(text)
    # Filter out valid K-numbers that might match
    malformed = []
    for m in matches:
        normalized = re.sub(r"\s", "", m)
        if not K_NUMBER_PATTERN.fullmatch(normalized):
            malformed.append(m.strip())
    return malformed


def extract_predicates_from_text_single(
    device_id: str, device: DeviceEntry
) -> ExtractionResult:
    try:
        text_path = TEXT_PATH / f"{device_id}.json"
        if not text_path.exists():
            return ExtractionResult(
                device_id=device_id,
                predicates=[],
                malformed_predicates=[],
                extraction_method="none",
            )

        if device_id.startswith("DEN"):
            return ExtractionResult(
                device_id=device_id,
                predicates=[],
                malformed_predicates=[],
                extraction_method="none",
            )

        text_data = json.loads(text_path.read_text())
        text = text_data["text"]
        predicates = extract_k_numbers(text)
        predicates = [k.upper() for k in predicates]
        predicates = [k for k in predicates if k != device_id]

        malformed_predicates = find_malformed_k_numbers(text)
        malformed_predicates = [k.upper() for k in malformed_predicates]
        malformed_predicates = [k for k in malformed_predicates if k != device_id]

        # uppercase all predicates
        return ExtractionResult(
            device_id=device_id,
            predicates=predicates,
            malformed_predicates=malformed_predicates,
            extraction_method=text_data["method"],
        )
    except Exception as e:
        return ExtractionResult(
            device_id=device_id,
            predicates=[],
            malformed_predicates=[],
            extraction_method="none",
            error=str(e),
        )


def extract_predicates_from_text(
    device_entries: list[tuple[str, DeviceEntry]],
) -> list[ExtractionResult]:
    with ProcessPoolExecutor() as executor:
        futures = [
            executor.submit(extract_predicates_from_text_single, device_id, device)
            for device_id, device in device_entries
        ]
        return [
            future.result()
            for future in tqdm.tqdm(as_completed(futures), total=len(futures))
        ]


def main():
    from lib import get_db, save_db

    db = get_db()
    device_entries = [(device_id, device) for device_id, device in db.devices.items()]
    results = extract_predicates_from_text(device_entries)
    for result in results:
        print(result)
        if result is not None:
            db.devices[result.device_id].predicates = result.predicates
            db.devices[result.device_id].malformed_predicates = (
                result.malformed_predicates
            )
            db.devices[result.device_id].extraction_method = result.extraction_method
    save_db(db)


if __name__ == "__main__":
    main()
