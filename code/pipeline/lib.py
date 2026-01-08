import pathlib
from typing import Literal
import pydantic

DATA_PATH = pathlib.Path(__file__).parent.parent.parent / "data"
DB_PATH = DATA_PATH / "devices.json"

FDA_JSON_PATH = DATA_PATH / "device-510k-0001-of-0001.json"
TEXT_PATH = DATA_PATH.parent / "device_text"
PDF_PATH = DATA_PATH.parent / "pdfs"

CONTACTS_PATH = DATA_PATH / "pmn96cur.txt"

GRAPH_PATH = DATA_PATH / "graph.json"
CYTOSCAPE_PATH = DATA_PATH / "cytoscape.json"


class DeviceEntry(pydantic.BaseModel):
    """Single device entry in db.json."""

    old_predicates: list[str] = pydantic.Field(default_factory=list)

    # pdf fields
    has_pdf: bool | None = None
    pdf_downloaded: bool = False
    pdf_chars: int = 0
    pdf_pages: int = 0
    pdf_char_density: float = 0.0
    pdf_label: str = "unknown"

    # textification
    extraction_method: str

    # predicates
    predicates: list[str] = pydantic.Field(default_factory=list)
    malformed_predicates: list[str] = pydantic.Field(default_factory=list)


class Database(pydantic.BaseModel):
    """Database of device entries."""

    devices: dict[str, DeviceEntry] = pydantic.Field(default_factory=dict)


def get_db() -> Database:
    """Get the database from the data/db.json file."""
    with DB_PATH.open("r") as f:
        return Database.model_validate_json(f.read())


def save_db(db: Database) -> None:
    """Save the database to the data/db.json file."""
    # sort the devices by device_id
    db.devices = dict(sorted(db.devices.items(), key=lambda x: x[0]))
    with DB_PATH.open("w") as f:
        f.write(db.model_dump_json(indent=2))
