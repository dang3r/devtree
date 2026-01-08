import pathlib
import pydantic

DATA_PATH = pathlib.Path(__file__).parent.parent.parent / "data"
DB_PATH = DATA_PATH / "devices.json"

FDA_JSON_PATH = DATA_PATH / "device-510k-0001-of-0001.json"


class DeviceEntry(pydantic.BaseModel):
    """Single device entry in db.json."""

    old_predicates: list[str] = pydantic.Field(default_factory=list)
    has_pdf: bool | None = None
    pdf_downloaded: bool = False

    pdf_chars: int = 0
    pdf_pages: int = 0
    pdf_char_density: float = 0.0


class Database(pydantic.BaseModel):
    """Database of device entries."""

    devices: dict[str, DeviceEntry] = pydantic.Field(default_factory=dict)


def get_db() -> Database:
    """Get the database from the data/db.json file."""
    with DB_PATH.open("r") as f:
        return Database.model_validate_json(f.read())


def save_db(db: Database) -> None:
    """Save the database to the data/db.json file."""
    with DB_PATH.open("w") as f:
        f.write(db.model_dump_json(indent=2))
