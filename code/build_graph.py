#!/usr/bin/env python3
"""
Build the final device graph JSON by merging FDA metadata with extracted predicates.

Outputs a graph structure with:
- nodes: dict of k_number -> device metadata
- edges: list of {source, target} predicate relationships
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel


class DeviceNode(BaseModel):
    """Metadata for a single device node."""

    device_name: str
    applicant: str
    contact: str | None
    decision_date: str | None
    device_class: str | None
    product_code: str | None
    advisory_committee: str | None
    specialty: str | None
    date_received: str | None
    decision_description: str | None
    clearance_type: str | None
    country_code: str | None
    state: str | None
    regulation_number: str | None


class Edge(BaseModel):
    """A predicate relationship edge."""

    source: str
    target: str


class GraphMetadata(BaseModel):
    """Metadata about the generated graph."""

    generated_at: str
    total_nodes: int
    total_edges: int
    nodes_with_predicates: int
    nodes_without_predicates: int
    orphan_predicates: int  # predicates that reference non-existent devices


class DeviceGraph(BaseModel):
    """The complete device graph structure."""

    metadata: GraphMetadata
    nodes: dict[str, DeviceNode]
    edges: list[Edge]


def load_fda_data(path: Path) -> dict[str, dict[str, Any]]:
    """Load FDA device data and index by k_number."""
    print(f"Loading FDA data from {path}...")
    with open(path) as f:
        data = json.load(f)

    devices = {}
    for device in data["results"]:
        k_num = device.get("k_number")
        if k_num:
            devices[k_num] = device

    print(f"  Loaded {len(devices):,} devices")
    return devices


def load_predicates(path: Path) -> dict[str, list[str]]:
    """Load predicate relationships."""
    print(f"Loading predicates from {path}...")
    with open(path) as f:
        data = json.load(f)

    predicates = {}
    for k_num, info in data.get("devices", {}).items():
        preds = info.get("predicates", [])
        if preds:
            predicates[k_num] = preds

    total_edges = sum(len(p) for p in predicates.values())
    print(f"  Loaded {len(predicates):,} devices with {total_edges:,} predicate links")
    return predicates


def load_contacts(path: Path) -> dict[str, str]:
    """Load contact info from pmn96cur.txt pipe-delimited file."""
    print(f"Loading contacts from {path}...")
    df = pd.read_csv(
        path, sep="|", dtype=str, usecols=["KNUMBER", "CONTACT"], encoding="latin-1"
    )
    df = df.dropna(subset=["CONTACT"])
    contacts = dict(zip(df["KNUMBER"], df["CONTACT"]))
    print(f"  Loaded {len(contacts):,} contacts")
    return contacts


def extract_device_node(device: dict[str, Any], contact: str | None = None) -> DeviceNode:
    """Extract relevant fields from FDA device data."""
    openfda = device.get("openfda", {})

    return DeviceNode(
        device_name=device.get("device_name", "Unknown"),
        applicant=device.get("applicant", "Unknown"),
        contact=contact,
        decision_date=device.get("decision_date"),
        device_class=openfda.get("device_class"),
        product_code=device.get("product_code"),
        advisory_committee=device.get("advisory_committee"),
        specialty=device.get("advisory_committee_description"),
        date_received=device.get("date_received"),
        decision_description=device.get("decision_description"),
        clearance_type=device.get("clearance_type"),
        country_code=device.get("country_code"),
        state=device.get("state"),
        regulation_number=openfda.get("regulation_number"),
    )


def build_graph(
    fda_devices: dict[str, dict[str, Any]],
    predicates: dict[str, list[str]],
    contacts: dict[str, str],
) -> DeviceGraph:
    """Build the complete device graph."""
    print("Building graph...")

    nodes: dict[str, DeviceNode] = {}
    edges: list[Edge] = []
    orphan_count = 0

    # Build nodes from FDA data
    for k_num, device in fda_devices.items():
        contact = contacts.get(k_num)
        nodes[k_num] = extract_device_node(device, contact)

    # Build edges from predicates
    for source, targets in predicates.items():
        for target in targets:
            edges.append(Edge(source=source, target=target))
            # Track orphan predicates (reference devices not in FDA data)
            if target not in fda_devices:
                orphan_count += 1

    # Count nodes with/without predicates
    nodes_with_preds = len(predicates)
    nodes_without_preds = len(nodes) - nodes_with_preds

    metadata = GraphMetadata(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_nodes=len(nodes),
        total_edges=len(edges),
        nodes_with_predicates=nodes_with_preds,
        nodes_without_predicates=nodes_without_preds,
        orphan_predicates=orphan_count,
    )

    return DeviceGraph(metadata=metadata, nodes=nodes, edges=edges)


def export_cytoscape(graph: DeviceGraph, output_path: Path) -> None:
    """Export graph in Cytoscape.js format. Filters out edges with missing nodes."""
    node_ids = set(graph.nodes.keys())

    # Filter edges to only include those where both source and target exist
    valid_edges = [e for e in graph.edges if e.source in node_ids and e.target in node_ids]
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
    with open(output_path, "w") as f:
        json.dump(cytoscape, f, indent=2)


def main() -> None:
    project_root = Path(__file__).parent.parent
    data_path = project_root / "data"

    # Load source data
    fda_devices = load_fda_data(data_path / "device-510k-0001-of-0001.json")
    predicates = load_predicates(data_path / "predicates.json")
    contacts = load_contacts(data_path / "pmn96cur.txt")

    # Build graph
    graph = build_graph(fda_devices, predicates, contacts)

    # Output stats
    print()
    print("=== Graph Statistics ===")
    print(f"Total nodes:           {graph.metadata.total_nodes:,}")
    print(f"Total edges:           {graph.metadata.total_edges:,}")
    print(f"Nodes with predicates: {graph.metadata.nodes_with_predicates:,}")
    print(f"Nodes w/o predicates:  {graph.metadata.nodes_without_predicates:,}")
    print(f"Orphan predicates:     {graph.metadata.orphan_predicates:,}")
    print()

    # Write outputs
    graph_path = data_path / "device_graph.json"
    print(f"Writing graph to {graph_path}...")
    with open(graph_path, "w") as f:
        json.dump(graph.model_dump(), f, indent=2)
    size_mb = graph_path.stat().st_size / (1024 * 1024)
    print(f"  Size: {size_mb:.1f} MB")

    cytoscape_path = data_path / "cytoscape_graph.json"
    print(f"Writing Cytoscape graph to {cytoscape_path}...")
    export_cytoscape(graph, cytoscape_path)
    size_mb = cytoscape_path.stat().st_size / (1024 * 1024)
    print(f"  Size: {size_mb:.1f} MB")

    print("Done!")


if __name__ == "__main__":
    main()
