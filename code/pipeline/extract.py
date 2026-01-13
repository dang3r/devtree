import json
import re
from concurrent.futures import ProcessPoolExecutor, as_completed

import tqdm
from pydantic import BaseModel

from lib import PREDICATES_OVERRIDES_PATH, PREDICATES_PATH, TEXT_PATH, DeviceEntry

# Case insensitive regex for K-numbers
K_NUMBER_PATTERN = re.compile(r"((k|den)\d{6})", re.IGNORECASE)
MALFORMED_PATTERN = re.compile(
    r"k\s*\d[\s\d]{5,8}", re.IGNORECASE
)  # K with spaces in digits


class ExtractionResult(BaseModel):
    """Complete extraction result for a single device."""

    device_id: str
    predicates: list[str]
    error: str | None = None


def extract_k_numbers(text: str) -> list[str]:
    """Find all unique K-numbers."""
    matches = K_NUMBER_PATTERN.findall(text)
    matches = [m[0] for m in matches]
    return list(set(matches))


def extract_predicates_from_text_single(device_id: str) -> ExtractionResult | None:
    try:
        # Skip DEN devices (De Novo, don't have predicates)
        if device_id.startswith("DEN"):
            return None

        # Read plain .txt file
        text_path = TEXT_PATH / f"{device_id}.txt"
        if not text_path.exists():
            return None

        text = text_path.read_text()
        predicates = extract_k_numbers(text)
        predicates = [k.upper() for k in predicates]
        predicates = [k for k in predicates if k != device_id]

        return ExtractionResult(
            device_id=device_id,
            predicates=predicates,
        )
    except Exception as e:
        return ExtractionResult(
            device_id=device_id,
            predicates=[],
            error=str(e),
        )


def extract_predicates_from_text(
    device_ids: list[str],
) -> list[ExtractionResult | None]:
    with ProcessPoolExecutor() as executor:
        futures = [
            executor.submit(extract_predicates_from_text_single, device_id)
            for device_id in device_ids
        ]
        return [
            future.result()
            for future in tqdm.tqdm(as_completed(futures), total=len(futures))
        ]


def main():
    # identify all text files in text directory
    device_ids = [p.stem for p in TEXT_PATH.glob("*.txt")]
    results = extract_predicates_from_text(device_ids)

    did_to_predicates = {}
    for result in results:
        if result is None:
            continue
        did_to_predicates[result.device_id] = {}
        did_to_predicates[result.device_id]["predicates"] = result.predicates
        did_to_predicates[result.device_id]["method"] = "regex_rawtext"

    with open("data/predicates_regex_rawtext.json", "w") as f:
        json.dump(did_to_predicates, f, indent=2)


if __name__ == "__main__":
    main()
