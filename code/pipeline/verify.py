#!/usr/bin/env python3
"""
Manual verification CLI for device predicates.

Allows marking devices as human-verified with optionally corrected predicates.

Usage:
    uv run code/pipeline/verify.py K123456 --predicates K111111,K222222
    uv run code/pipeline/verify.py K123456 --show
    uv run code/pipeline/verify.py --list-flagged
"""

import argparse
import sys
from pathlib import Path

from .db import load_db, save_db, set_human_verified


def get_default_db_path() -> Path:
    """Get default db.json path."""
    return Path(__file__).parent.parent.parent / "data" / "db.json"


def show_device(db_path: Path, k_number: str) -> int:
    """Show current state of a device."""
    db = load_db(db_path)

    if k_number not in db.devices:
        print(f"Device {k_number} not found in database")
        return 1

    entry = db.devices[k_number]
    print(f"\nDevice: {k_number}")
    print(f"  Predicates: {entry.predicates or '(none)'}")
    print(f"  Human verified: {entry.human_verified}")
    print(f"  PDF present: {entry.pdf_present}")
    print(f"  Extraction method: {entry.extraction_method or '(none)'}")
    print(f"  Text length: {entry.text_length}")
    print(f"  Chars/page: {entry.chars_per_page}")
    print(f"  Flags: {entry.flags or '(none)'}")
    if entry.errors.download_error:
        print(f"  Download error: {entry.errors.download_error}")
    if entry.errors.extraction_error:
        print(f"  Extraction error: {entry.errors.extraction_error}")
    if entry.errors.ocr_error:
        print(f"  OCR error: {entry.errors.ocr_error}")
    print()

    return 0


def verify_device(
    db_path: Path,
    k_number: str,
    predicates: list[str] | None,
) -> int:
    """Mark a device as human verified."""
    db = load_db(db_path)

    if k_number not in db.devices:
        print(f"Device {k_number} not found in database")
        return 1

    entry = db.devices[k_number]
    old_predicates = entry.predicates.copy()

    success = set_human_verified(db, k_number, predicates)
    if not success:
        print(f"Failed to verify device {k_number}")
        return 1

    save_db(db, db_path)

    print(f"\nDevice {k_number} marked as human verified")
    if predicates is not None:
        print(f"  Old predicates: {old_predicates or '(none)'}")
        print(f"  New predicates: {predicates or '(none)'}")
    print()

    return 0


def list_flagged(db_path: Path, limit: int = 50) -> int:
    """List devices with flags that may need review."""
    db = load_db(db_path)

    flagged = [
        (k_num, entry)
        for k_num, entry in db.devices.items()
        if entry.flags and not entry.human_verified
    ]

    if not flagged:
        print("No flagged devices needing review")
        return 0

    print(f"\nFlagged devices needing review ({len(flagged)} total):\n")

    for k_num, entry in sorted(flagged)[:limit]:
        flags_str = ", ".join(entry.flags)
        preds_str = f"{len(entry.predicates)} predicates" if entry.predicates else "no predicates"
        print(f"  {k_num}: {flags_str} ({preds_str})")

    if len(flagged) > limit:
        print(f"\n  ... and {len(flagged) - limit} more")

    print()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Manual verification CLI for device predicates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "k_number",
        nargs="?",
        help="K-number to verify or show",
    )
    parser.add_argument(
        "--predicates",
        type=str,
        help="Comma-separated list of predicate K-numbers (e.g., K111111,K222222)",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Show current state of the device without modifying",
    )
    parser.add_argument(
        "--list-flagged",
        action="store_true",
        help="List flagged devices needing review",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=get_default_db_path(),
        help="Path to db.json",
    )

    args = parser.parse_args()

    if args.list_flagged:
        return list_flagged(args.db)

    if not args.k_number:
        parser.print_help()
        return 1

    if args.show:
        return show_device(args.db, args.k_number)

    # Parse predicates
    predicates = None
    if args.predicates is not None:
        predicates = [p.strip() for p in args.predicates.split(",") if p.strip()]

    return verify_device(args.db, args.k_number, predicates)


if __name__ == "__main__":
    sys.exit(main())
