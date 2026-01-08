# read db.json
import json
from pathlib import Path

pdf_paths = Path("pdfs").glob("*.pdf")
device_ids_with_pdfs = set([p.stem for p in pdf_paths])
print(device_ids_with_pdfs)


data = json.load(open("data/db.json"))

# filter for devices with predicates

# save to file
# get all

new_data = dict(devices=dict())
for device_id, device_data in data["devices"].items():
    new_data["devices"][device_id] = {
        "old_predicates": device_data["predicates"],
        "has_pdf": (device_id in device_ids_with_pdfs) or None,
        "pdf_downloaded": device_id in device_ids_with_pdfs,
    }

with open("devices.json", "w") as f:
    json.dump(new_data, f, indent=2)
