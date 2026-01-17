import json
import pathlib

import pydantic

DATA_PATH = pathlib.Path(__file__).parent.parent.parent / "data"
TEXT_PATH = DATA_PATH.parent / "text"
DB_PATH = DATA_PATH / "devices.json"

PDF_DATA_PATH = DATA_PATH / "pdf.json"

FDA_JSON_PATH = DATA_PATH / "device-510k-0001-of-0001.json"
PDF_PATH = DATA_PATH.parent / "pdfs"


GRAPH_PATH = DATA_PATH / "graph.json"
CYTOSCAPE_PATH = DATA_PATH / "cytoscape.json"
PREDICATES_PATH = DATA_PATH / "predicates.json"

RAWTEXT_PATH = TEXT_PATH / "pymupdf"
MINISTRAL3_3B_PATH = TEXT_PATH / "ministral3_3b"
TESSERACT_TEXT_PATH = TEXT_PATH / "tesseract"

PREDICATES_PATH = DATA_PATH.parent / "predicates"


PREDICATES_OVERRIDES_PATH = DATA_PATH / "predicate_overrides.json"
PREDICATES_RAWTEXT_PATH = DATA_PATH / "predicates_regex_rawtext.json"
PREDICATES_CLAUDECODE_PATH = DATA_PATH / "predicates_claudecode.json"
PREDICATES_MINISTRAL3_3B_PATH = DATA_PATH / "predicates_regex_ministral3_3b.json"

PREDICATES_CLAUDECODE_PATH = PREDICATES_PATH / "claude_code"


def get_predicates_rawtext(
    path: pathlib.Path = PREDICATES_RAWTEXT_PATH,
) -> dict[str, list[str]]:
    return json.loads(path.read_text())


def get_claudecode_predicates(
    path: pathlib.Path = PREDICATES_CLAUDECODE_PATH,
) -> dict[str, list[str]]:
    with open(path) as f:
        data = json.load(f)

    return {
        k: {"predicates": v["predicates"], "method": v["method"]}
        for k, v in data.items()
    }


def get_human_predicates(
    path: pathlib.Path = PREDICATES_OVERRIDES_PATH,
) -> dict[str, list[str]]:
    return json.loads(path.read_text())


def get_ministral3_3b_predicates(
    path: pathlib.Path = PREDICATES_MINISTRAL3_3B_PATH,
) -> dict[str, list[str]]:
    return json.loads(path.read_text())


def get_predicates():
    rawtext_predicates = get_predicates_rawtext()
    claudecode_predicates = get_claudecode_predicates()
    human_predicates = get_human_predicates()
    ministral3_3b_predicates = get_ministral3_3b_predicates()
    return {
        **rawtext_predicates,
        **ministral3_3b_predicates,
        **claudecode_predicates,
        **human_predicates,
    }
