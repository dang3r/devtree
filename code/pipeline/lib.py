import json
import pathlib

import pydantic

DATA_PATH = pathlib.Path(__file__).parent.parent.parent / "data"
DB_PATH = DATA_PATH / "devices.json"

FDA_JSON_PATH = DATA_PATH / "device-510k-0001-of-0001.json"
TEXT_PATH = DATA_PATH.parent / "device_text"
PDF_PATH = DATA_PATH.parent / "pdfs"

CONTACTS_PATH = DATA_PATH / "pmn96cur.txt"

GRAPH_PATH = DATA_PATH / "graph.json"
CYTOSCAPE_PATH = DATA_PATH / "cytoscape.json"
PREDICATES_PATH = DATA_PATH / "predicates.json"


class PDFState(pydantic.BaseModel):
    """Tracks PDF download state."""

    exists: bool | None = None  # Does FDA have a PDF for this device?
    downloaded: bool = False  # Have we fetched it locally?
    pages: int = 0
    chars: int = 0
    density: float = 0.0  # chars/page ratio
    quality: str = "unknown"  # "rich" | "sparse" | "empty"


class TextState(pydantic.BaseModel):
    """Tracks text extraction state."""

    extracted: bool = False
    method: str | None = None  # "pymupdf" | "ollama_ministral-3-3b" | etc.


class PredicateState(pydantic.BaseModel):
    """Tracks predicate extraction state."""

    extracted: bool = False  # Have we run K-number extraction?
<<<<<<< HEAD

    values: list[str] = pydantic.Field(default_factory=list)  # Valid K-numbers
    malformed: list[str] = pydantic.Field(default_factory=list)  # Partial matches

    @pydantic.field_serializer("values")
    def serialize_values(self, values: list[str]) -> list[str]:
        return sorted(values)

    @pydantic.field_serializer("malformed")
    def serialize_malformed(self, malformed: list[str]) -> list[str]:
        return sorted(malformed)
=======
    values: list[str] = pydantic.Field(default_factory=list)  # Valid K-numbers
    malformed: list[str] = pydantic.Field(default_factory=list)  # Partial matches
>>>>>>> master


class DeviceEntry(pydantic.BaseModel):
    """Single device entry in devices.json."""

    pdf: PDFState = pydantic.Field(default_factory=PDFState)
    text: TextState = pydantic.Field(default_factory=TextState)
    preds: PredicateState = pydantic.Field(default_factory=PredicateState)


class Database(pydantic.BaseModel):
    """Database of device entries."""

    devices: dict[str, DeviceEntry] = pydantic.Field(default_factory=dict)

<<<<<<< HEAD
    @pydantic.field_serializer("devices")
    def serialize_devices(
        self, devices: dict[str, DeviceEntry]
    ) -> dict[str, DeviceEntry]:
        return dict(sorted(devices.items(), key=lambda x: x[0]))


def get_db(path: pathlib.Path = DB_PATH) -> Database:
    """Load database with Pydantic validation."""
    data = json.loads(path.read_text())
    return Database.model_validate(data)


=======

def get_db(path: pathlib.Path = DB_PATH) -> Database:
    """Load database with Pydantic validation."""
    data = json.loads(path.read_text())
    return Database.model_validate(data)


>>>>>>> master
def save_db(db: Database, path: pathlib.Path = DB_PATH) -> None:
    """Atomic write with temp file swap."""
    db.devices = dict(sorted(db.devices.items(), key=lambda x: x[0]))
    tmp = path.with_suffix(".tmp")
    tmp.write_text(db.model_dump_json(indent=2))
    tmp.replace(path)  # Atomic on POSIX filesystems


def get_predicates(path: pathlib.Path = PREDICATES_PATH) -> dict[str, list[str]]:
    """Load predicates from versioned file."""
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_predicates(
    predicates: dict[str, list[str]], path: pathlib.Path = PREDICATES_PATH
) -> None:
    """Save predicates to versioned file (atomic write)."""
    sorted_preds = dict(sorted(predicates.items()))
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(sorted_preds, indent=2))
    tmp.replace(path)
