"""
Build device graph from FDA data and predicates.

Creates a graph structure with nodes (devices) and edges (predicate relationships).
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel


class DeviceNode(BaseModel):
    """Device node metadata."""

    device_name: str
    applicant: str
    contact: str | None = None
    decision_date: str | None = None
    device_class: str | None = None
    product_code: str | None = None
    specialty: str | None = None
    date_received: str | None = None
    # decision_description: str | None = None
    country_code: str | None = None
    state: str | None = None


class Edge(BaseModel):
    """Predicate relationship edge."""

    source: str
    target: str


class GraphMetadata(BaseModel):
    """Graph metadata."""

    generated_at: str
    total_nodes: int
    total_edges: int
    nodes_with_predicates: int
    nodes_without_predicates: int
    orphan_predicates: int


class DeviceGraph(BaseModel):
    """Complete device graph."""

    metadata: GraphMetadata
    nodes: dict[str, DeviceNode]
    edges: list[Edge]


def load_fda_data(path: Path) -> dict[str, dict[str, Any]]:
    """Load FDA device data indexed by K-number."""
    print(f"Loading FDA data from {path}...")
    with open(path) as f:
        data = json.load(f)

    devices = {}
    for device in data.get("results", []):
        k_num = device.get("k_number")
        if k_num:
            devices[k_num] = device

    print(f"  Loaded {len(devices):,} devices")
    return devices


def load_predicates(path: Path) -> dict[str, list[str]]:
    """Load predicate relationships from predicates.json (simple format)."""
    print(f"Loading predicates from {path}...")
    with open(path) as f:
        predicates = json.load(f)

    print(f"  Loaded {len(predicates):,} devices with predicates")
    return predicates


def load_predicates_from_db(path: Path) -> dict[str, list[str]]:
    """Load predicate relationships from devices.json."""
    print(f"Loading predicates from devices.json at {path}...")
    with open(path) as f:
        data = json.load(f)

    predicates = {}
    for k_num, entry in data.get("devices", {}).items():
        # New nested format: entry.preds.values
        preds_data = entry.get("preds", {})
        preds = preds_data.get("values", [])
        if preds:
            predicates[k_num] = preds

    print(f"  Loaded {len(predicates):,} devices with predicates")
    return predicates


def load_contacts(path: Path) -> dict[str, str]:
    """Load contact info from pmn96cur.txt."""
    if not path.exists():
        print(f"  No contacts file at {path}")
        return {}

    print(f"Loading contacts from {path}...")
    df = pd.read_csv(
        path, sep="|", dtype=str, usecols=["KNUMBER", "CONTACT"], encoding="latin-1"
    )
    df = df.dropna(subset=["CONTACT"])
    contacts = dict(zip(df["KNUMBER"], df["CONTACT"]))
    print(f"  Loaded {len(contacts):,} contacts")
    return contacts


def load_company_mappings(path: Path) -> dict[str, str]:
    """Load company name normalization mappings."""
    if not path.exists():
        return {}

    print(f"Loading company mappings from {path}...")
    with open(path) as f:
        mappings = json.load(f)

    # Build reverse lookup
    reverse = {}
    for canonical, variants in mappings.items():
        for variant in variants:
            reverse[variant] = canonical

    print(f"  Loaded {len(mappings):,} canonical names")
    return reverse


def extract_device_node(
    device: dict[str, Any],
) -> DeviceNode:
    """Extract DeviceNode from FDA device data."""
    openfda = device.get("openfda", {})
    applicant = device.get("applicant", "Unknown")

    return DeviceNode(
        device_name=device.get("device_name", "Unknown"),
        applicant=applicant,
        contact=device.get("contact"),
        decision_date=device.get("decision_date"),
        device_class=openfda.get("device_class"),
        product_code=device.get("product_code"),
        # advisory_committee=device.get("advisory_committee"),
        specialty=device.get("advisory_committee_description"),
        date_received=device.get("date_received"),
        # decision_description=device.get("decision_description"),
        # clearance_type=device.get("clearance_type"),
        country_code=device.get("country_code"),
        state=device.get("state"),
        # regulation_number=openfda.get("regulation_number"),
    )


def build_graph(
    fda_data_path: Path,
    predicates: dict,
) -> DeviceGraph:
    """
    Build the complete device graph.

    Args:
        fda_data_path: Path to FDA device JSON
        predicates_path: Path to predicates.json or db.json
        contacts_path: Optional path to pmn96cur.txt
        company_mappings_path: Optional path to company_mappings.json
        use_db_format: If True, load from db.json format instead of predicates.json
    """
    # Load data
    fda_devices = load_fda_data(fda_data_path)
    print("Building graph...")

    nodes: dict[str, DeviceNode] = {}
    edges: list[Edge] = []
    orphan_count = 0

    # Build nodes
    for k_num, device in fda_devices.items():
        nodes[k_num] = extract_device_node(device)

    # Build edges
    for source, targets in predicates.items():
        for target in targets:
            edges.append(Edge(source=source, target=target))
            if target not in fda_devices:
                orphan_count += 1

    metadata = GraphMetadata(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_nodes=len(nodes),
        total_edges=len(edges),
        nodes_with_predicates=len(predicates),
        nodes_without_predicates=len(nodes) - len(predicates),
        orphan_predicates=orphan_count,
    )

    print(f"  Nodes: {metadata.total_nodes:,}")
    print(f"  Edges: {metadata.total_edges:,}")
    print(f"  Orphan predicates: {orphan_count:,}")

    return DeviceGraph(metadata=metadata, nodes=nodes, edges=edges)


def export_graph(graph: DeviceGraph, output_path: Path) -> None:
    """Export graph to JSON."""
    print(f"Writing graph to {output_path}...")
    with open(output_path, "w") as f:
        json.dump(graph.model_dump(), f, indent=2)
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"  Size: {size_mb:.1f} MB")


def export_cytoscape(graph: DeviceGraph, output_path: Path) -> None:
    """Export graph in Cytoscape.js format."""
    node_ids = set(graph.nodes.keys())

    # Filter edges to only valid ones
    valid_edges = [
        e for e in graph.edges if e.source in node_ids and e.target in node_ids
    ]

    # save bad edges to a file
    bad_edges_path = Path("bad_edges.json")
    with open(bad_edges_path, "w") as f:
        json.dump(
            [
                e.model_dump()
                for e in graph.edges
                if e.source not in node_ids or e.target not in node_ids
            ],
            f,
            indent=2,
        )
    skipped = len(graph.edges) - len(valid_edges)
    if skipped > 0:
        print(f"  Skipped {skipped:,} edges with missing nodes")

    cytoscape = {
        "metadata": graph.metadata.model_dump(),
        "elements": {
            "nodes": [
                {"data": {"id": k_num, **node.model_dump()}}
                for k_num, node in graph.nodes.items()
            ],
            "edges": [
                {
                    "data": {
                        "id": f"e{i}",
                        "source": e.source,
                        "target": e.target,
                        "relationship": "predicate",
                    }
                }
                for i, e in enumerate(valid_edges)
            ],
        },
    }

    print(f"Writing Cytoscape graph to {output_path}...")
    with open(output_path, "w") as f:
        json.dump(cytoscape, f, indent=2)
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"  Size: {size_mb:.1f} MB")


def main():
    from lib import (
        CONTACTS_PATH,
        CYTOSCAPE_PATH,
        FDA_JSON_PATH,
        GRAPH_PATH,
        get_predicates,
    )

    raw_predicates = get_predicates()

    predicates = {k: v["predicates"] for k, v in raw_predicates.items()}

    graph = build_graph(
        FDA_JSON_PATH,
        predicates,
    )
    export_graph(graph, GRAPH_PATH)
    export_cytoscape(graph, CYTOSCAPE_PATH)


if __name__ == "__main__":
    main()
