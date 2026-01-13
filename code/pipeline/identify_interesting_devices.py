import json
from pathlib import Path
from lib import get_predicates


def main():
    """Try to identify devices that might require additional review of their predicates"""
    predicates = get_predicates()
    interesting_devices = []
    for device_id, data in predicates.items():
        if (
            len(data["predicates"]) == 0
            and device_id.startswith(("K0", "K1", "K2"))
            and data["method"] == "regex_rawtext"
        ):
            interesting_devices.append(device_id)

    print(f"Found {len(interesting_devices)} interesting devices")
    print(interesting_devices)


if __name__ == "__main__":
    main()
