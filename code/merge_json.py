#!/usr/bin/env python3
"""Merge all JSON files in a directory into a single JSON file."""

import argparse
import json
from pathlib import Path


def merge_json_files(directory: Path) -> list | dict:
    """Merge all JSON files in directory into a single structure.

    If all files contain lists, concatenates them.
    If all files contain dicts, merges them (later files override earlier).
    """
    json_files = sorted(directory.glob("*.json"))

    if not json_files:
        print(f"No JSON files found in {directory}")
        return []

    print(f"Found {len(json_files)} JSON files")

    merged: list | dict | None = None

    for path in json_files:
        print(f"  Processing: {path.name}")
        stem = path.stem
        with open(path) as f:
            data = json.load(f)

        new_data = {
            stem: data,
        }

        if merged is None:
            merged = new_data
        elif isinstance(merged, list) and isinstance(new_data, list):
            merged.extend(new_data)
        elif isinstance(merged, dict) and isinstance(new_data, dict):
            merged.update(new_data)
        else:
            raise TypeError(
                f"Cannot merge {type(merged).__name__} with {type(data).__name__}"
            )

    return merged if merged is not None else []


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge JSON files in a directory")
    parser.add_argument("directory", type=Path, help="Directory containing JSON files")
    parser.add_argument(
        "-o", "--output", type=Path, help="Output file (default: stdout)"
    )
    args = parser.parse_args()

    if not args.directory.is_dir():
        print(f"Error: {args.directory} is not a directory")
        return

    merged = merge_json_files(args.directory)

    output = json.dumps(merged, indent=2)

    if args.output:
        args.output.write_text(output)
        print(f"Wrote merged JSON to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
