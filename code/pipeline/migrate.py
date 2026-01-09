"""Migration and rebuild script for devices.json.

Can:
- Migrate old flat format to new nested structure
- Rebuild devices.json from sources (FDA data, PDFs, text files, predicates.json)
- Export predicates.json from current data
"""

import json
import pathlib
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from lib import (
    DB_PATH,
    FDA_JSON_PATH,
    PDF_PATH,
    PREDICATES_PATH,
    TEXT_PATH,
    Database,
    DeviceEntry,
    PDFState,
    PredicateState,
    TextState,
    get_predicates,
    save_db,
    save_predicates,
)


def build_device_entry(
    device_id: str,
    pdf_exists: bool,
    predicates: list[str] | None = None,
) -> DeviceEntry:
    """Build a device entry from source files."""
    # Check for text file (.txt or legacy .json)
    text_txt = TEXT_PATH / f"{device_id}.txt"
    text_json = TEXT_PATH / f"{device_id}.json"
    text_method: str | None = None
    text_extracted = False

    if text_txt.exists():
        text_extracted = True
        text_method = "pymupdf"  # Default, actual method tracked in predicates.json era
    elif text_json.exists():
        try:
            data = json.loads(text_json.read_text())
            text_method = data.get("method")
            text_extracted = True
        except (json.JSONDecodeError, KeyError):
            pass

    preds = predicates or []
    return DeviceEntry(
        pdf=PDFState(
            exists=pdf_exists,
            downloaded=pdf_exists,
        ),
        text=TextState(
            extracted=text_extracted,
            method=text_method,
        ),
        preds=PredicateState(
            extracted=len(preds) > 0,
            values=preds,
        ),
    )


def convert_text_file(json_path: pathlib.Path) -> tuple[str, bool]:
    """Convert device_text/*.json to *.txt. Returns (device_id, success)."""
    device_id = json_path.stem
    txt_path = json_path.with_suffix(".txt")

    try:
        data = json.loads(json_path.read_text())
        text = data.get("text", "")
        txt_path.write_text(text)
        json_path.unlink()  # Remove old JSON file
        return device_id, True
    except Exception as e:
        print(f"  Error converting {device_id}: {e}")
        return device_id, False


def rebuild() -> int:
    """Rebuild devices.json from source files."""
    print("=== Rebuilding devices.json ===\n")

    # Step 1: Load FDA data
    print("1. Loading FDA device data...")
    fda_device_ids: set[str] = set()
    if FDA_JSON_PATH.exists():
        fda_data = json.loads(FDA_JSON_PATH.read_text())
        for device in fda_data.get("results", []):
            k_number = device.get("k_number")
            if k_number:
                fda_device_ids.add(k_number)
        print(f"   Found {len(fda_device_ids)} devices in FDA data")
    else:
        print("   WARNING: FDA data file not found")

    # Step 2: Scan PDF directory
    print("\n2. Scanning PDF directory...")
    existing_pdfs = {p.stem for p in PDF_PATH.glob("*.pdf")}
    print(f"   Found {len(existing_pdfs)} PDF files on disk")

    # Step 3: Load predicates from versioned file
    print("\n3. Loading predicates.json...")
    predicates = get_predicates()
    print(f"   Found {len(predicates)} devices with predicates")

    # Step 4: Combine all device IDs
    all_device_ids = fda_device_ids | existing_pdfs | set(predicates.keys())
    print(f"\n4. Total unique devices: {len(all_device_ids)}")

    # Step 5: Build device entries
    print("\n5. Building device entries...")
    new_devices: dict[str, DeviceEntry] = {}

    for device_id in all_device_ids:
        pdf_exists = device_id in existing_pdfs
        preds = predicates.get(device_id)
        new_devices[device_id] = build_device_entry(device_id, pdf_exists, preds)

    # Stats
    with_pdf = sum(1 for e in new_devices.values() if e.pdf.downloaded)
    with_text = sum(1 for e in new_devices.values() if e.text.extracted)
    with_preds = sum(1 for e in new_devices.values() if e.preds.values)
    print(f"   - With PDF: {with_pdf}")
    print(f"   - With text: {with_text}")
    print(f"   - With predicates: {with_preds}")

    # Step 6: Save devices.json
    print("\n6. Saving devices.json...")
    db = Database(devices=new_devices)
    save_db(db)
    print(f"   Saved {len(new_devices)} devices")

    return 0


def export_predicates() -> int:
    """Export predicates from current devices.json to predicates.json."""
    print("=== Exporting predicates.json ===\n")

    if not DB_PATH.exists():
        print("ERROR: devices.json not found")
        return 1

    print("Loading devices.json...")
    data = json.loads(DB_PATH.read_text())
    devices = data.get("devices", {})

    predicates: dict[str, list[str]] = {}
    for device_id, entry in devices.items():
        # Handle both old flat format and new nested format
        if "preds" in entry:
            preds = entry["preds"].get("values", [])
        else:
            preds = entry.get("predicates", [])

        if preds:
            predicates[device_id] = preds

    print(f"Found {len(predicates)} devices with predicates")

    save_predicates(predicates)
    print(f"Saved to {PREDICATES_PATH}")

    return 0


def main() -> int:
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "rebuild":
            return rebuild()
        elif cmd == "export-predicates":
            return export_predicates()
        else:
            print(f"Unknown command: {cmd}")
            print("Usage: migrate.py [rebuild|export-predicates]")
            return 1

    # Default: export predicates then rebuild
    print("Running: export-predicates then rebuild\n")
    ret = export_predicates()
    if ret != 0:
        return ret
    print()
    return rebuild()


if __name__ == "__main__":
    sys.exit(main())
