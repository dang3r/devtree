#!/usr/bin/env python3
"""
Migrate existing data to new db.json format.

Converts predicates.json, suspicious.json, and manifest.json into the unified
db.json structure.
"""

import argparse
import json
import sys
from pathlib import Path

from .db import DeviceDatabase, DeviceEntry, DeviceErrors, save_db


def migrate_predicates_to_db(
    predicates_path: Path,
    suspicious_path: Path | None,
    manifest_path: Path | None,
    output_db_path: Path,
) -> DeviceDatabase:
    """Migrate existing data to new db.json format."""
    db = DeviceDatabase()

    # Load predicates.json
    if predicates_path.exists():
        print(f"Loading predicates from {predicates_path}...")
        with open(predicates_path) as f:
            pred_data = json.load(f)

        devices_data = pred_data.get("devices", {})
        for k_num, info in devices_data.items():
            entry = DeviceEntry(
                predicates=info.get("predicates", []),
                extraction_method="pymupdf",
                text_length=info.get("text_length", 0),
            )
            db.devices[k_num] = entry

        print(f"  Loaded {len(devices_data)} devices from predicates.json")
    else:
        print(f"Warning: {predicates_path} not found")

    # Load manifest.json to set pdf_present
    if manifest_path and manifest_path.exists():
        print(f"Loading manifest from {manifest_path}...")
        with open(manifest_path) as f:
            manifest = json.load(f)

        results = manifest.get("results", {})
        pdf_present_count = 0
        pdf_failed_count = 0

        for k_num, info in results.items():
            status = info.get("status", "")
            if k_num in db.devices:
                db.devices[k_num].pdf_present = status == "success"
                if status == "success":
                    pdf_present_count += 1
                else:
                    pdf_failed_count += 1
                    if info.get("error"):
                        db.devices[k_num].errors.download_error = info["error"]
            else:
                # Device in manifest but not in predicates - add it
                entry = DeviceEntry(
                    pdf_present=status == "success",
                )
                if info.get("error"):
                    entry.errors.download_error = info["error"]
                db.devices[k_num] = entry

        print(f"  PDF present: {pdf_present_count}, failed: {pdf_failed_count}")
    elif manifest_path:
        print(f"Warning: {manifest_path} not found")

    # Load suspicious.json to add flags
    if suspicious_path and suspicious_path.exists():
        print(f"Loading suspicious flags from {suspicious_path}...")
        with open(suspicious_path) as f:
            susp_data = json.load(f)

        flagged_count = 0
        devices_list = susp_data.get("devices", [])

        for device in devices_list:
            k_num = device.get("k_number")
            if k_num and k_num in db.devices:
                flags = [f.get("reason", "") for f in device.get("flags", []) if f.get("reason")]
                db.devices[k_num].flags = flags
                flagged_count += 1

        print(f"  Added flags to {flagged_count} devices")
    elif suspicious_path:
        print(f"Warning: {suspicious_path} not found")

    # Save the new database
    print(f"\nSaving db.json to {output_db_path}...")
    save_db(db, output_db_path)

    print(f"\nMigration complete:")
    print(f"  Total devices: {db.total_devices}")
    print(f"  With predicates: {db.with_predicates}")
    print(f"  Without predicates: {db.without_predicates}")
    print(f"  PDF present: {db.pdf_present_count}")
    print(f"  Total predicate references: {db.total_predicate_references}")

    return db


def main():
    parser = argparse.ArgumentParser(description="Migrate to db.json format")
    parser.add_argument(
        "--predicates",
        type=Path,
        default=Path("data/predicates.json"),
        help="Path to predicates.json",
    )
    parser.add_argument(
        "--suspicious",
        type=Path,
        default=Path("data/suspicious.json"),
        help="Path to suspicious.json",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/manifest.json"),
        help="Path to manifest.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/db.json"),
        help="Output path for db.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without saving",
    )

    args = parser.parse_args()

    if args.dry_run:
        print("DRY RUN - no files will be written\n")

    # Check required file
    if not args.predicates.exists():
        print(f"Error: Required file {args.predicates} not found")
        sys.exit(1)

    if args.dry_run:
        # Just load and count without saving
        print(f"Would migrate:")
        print(f"  predicates: {args.predicates}")
        print(f"  suspicious: {args.suspicious}")
        print(f"  manifest: {args.manifest}")
        print(f"  output: {args.output}")
        sys.exit(0)

    migrate_predicates_to_db(
        args.predicates,
        args.suspicious if args.suspicious.exists() else None,
        args.manifest if args.manifest.exists() else None,
        args.output,
    )


if __name__ == "__main__":
    main()
