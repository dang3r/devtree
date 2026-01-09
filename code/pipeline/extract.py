import re
from concurrent.futures import ProcessPoolExecutor, as_completed

import tqdm
from pydantic import BaseModel

from lib import TEXT_PATH, DeviceEntry

# Case insensitive regex for K-numbers
K_NUMBER_PATTERN = re.compile(r"((k|den)\d{6})", re.IGNORECASE)
MALFORMED_PATTERN = re.compile(
    r"k\s*\d[\s\d]{5,8}", re.IGNORECASE
)  # K with spaces in digits


class ExtractionResult(BaseModel):
    """Complete extraction result for a single device."""

    device_id: str
    predicates: list[str]
    malformed: list[str]
    error: str | None = None


def extract_k_numbers(text: str) -> list[str]:
    """Find all unique K-numbers."""
    matches = K_NUMBER_PATTERN.findall(text)
    matches = [m[0] for m in matches]
    return list(set(matches))


def find_malformed_k_numbers(text: str) -> list[str]:
    """Find K-numbers with spaces or typos."""
    matches = MALFORMED_PATTERN.findall(text)
    malformed = []
    for m in matches:
        normalized = re.sub(r"\s", "", m)
        if not K_NUMBER_PATTERN.fullmatch(normalized):
            malformed.append(m.strip())
    return malformed


def extract_predicates_from_text_single(
    device_id: str, device: DeviceEntry
) -> ExtractionResult | None:
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

        malformed = find_malformed_k_numbers(text)
        malformed = [k.upper() for k in malformed]
        malformed = [k for k in malformed if k != device_id]

        return ExtractionResult(
            device_id=device_id,
            predicates=predicates,
            malformed=malformed,
        )
    except Exception as e:
        return ExtractionResult(
            device_id=device_id,
            predicates=[],
            malformed=[],
            error=str(e),
        )


def extract_predicates_from_text(
    device_entries: list[tuple[str, DeviceEntry]],
) -> list[ExtractionResult | None]:
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
    from lib import get_db, save_db, save_predicates

    db = get_db()
    device_entries = [(device_id, device) for device_id, device in db.devices.items()]
    results = extract_predicates_from_text(device_entries)

    for result in results:
        if result is None:
            continue
        entry = db.devices[result.device_id]
        entry.preds.extracted = True
        entry.preds.values = result.predicates
        entry.preds.malformed = result.malformed

    # Save full state to devices.json
    save_db(db)

    # Save predicates to versioned file
    predicates = {
        did: entry.preds.values
        for did, entry in db.devices.items()
        if entry.preds.values
    }
    save_predicates(predicates)
    print(f"Saved {len(predicates)} devices with predicates to predicates.json")


if __name__ == "__main__":
    main()
