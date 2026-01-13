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

    # sort by reverse
    interesting_devices.sort(reverse=True)

    print(f"Found {len(interesting_devices)} interesting devices")
    for device_id in interesting_devices:
        pass
        print(device_id)

    def get_pages(device_id):
        import fitz

        doc = fitz.open(f"pdfs/{device_id}.pdf")
        return len(doc)

    total_pages = 0
    for device_id in interesting_devices:
        total_pages += get_pages(device_id)

    print(f"Total pages: {total_pages}")


if __name__ == "__main__":
    main()
