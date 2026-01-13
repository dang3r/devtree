"""
Graph analysis for medical device predicate relationships.

Computes structural metrics and company-level analysis.
"""

import json
import re
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx
from pydantic import BaseModel
from tqdm import tqdm

from graph import DeviceGraph
from lib import DATA_PATH, GRAPH_PATH


class ChainInfo(BaseModel):
    """Information about a predicate chain."""

    chain: list[str]
    length: int
    start_device: str
    end_device: str
    start_year: int | None = None
    end_year: int | None = None
    span_years: int | None = None


class DeviceMetrics(BaseModel):
    """Metrics for a single device."""

    device_id: str
    in_degree: int
    out_degree: int
    applicant: str
    device_name: str


class CompanyMetrics(BaseModel):
    """Metrics for a company."""

    name: str
    total_devices: int
    devices_as_predicates: int
    total_predicate_citations: int
    unique_predicates_used: int
    cross_company_predicate_count: int
    cross_company_predicate_ratio: float


class CompanyRelationship(BaseModel):
    """Cross-company predicate relationship."""

    source_company: str
    target_company: str
    edge_count: int


class GraphStatistics(BaseModel):
    """Overall graph statistics."""

    total_nodes: int
    total_edges: int
    density: float
    num_weakly_connected_components: int
    largest_wcc_size: int
    num_root_nodes: int
    num_leaf_nodes: int
    avg_in_degree: float
    avg_out_degree: float
    max_in_degree: int
    max_out_degree: int


class AnalysisResults(BaseModel):
    """Complete analysis output."""

    generated_at: str
    graph_stats: GraphStatistics
    longest_chains: list[ChainInfo]
    most_cited_devices: list[DeviceMetrics]
    root_nodes: list[str]
    top_companies: list[CompanyMetrics]
    company_network: list[CompanyRelationship]


def load_device_graph(path: Path) -> DeviceGraph:
    """Load DeviceGraph from JSON file."""
    print(f"Loading graph from {path}...")
    with open(path) as f:
        data = json.load(f)
    graph = DeviceGraph.model_validate(data)
    print(f"  Loaded {len(graph.nodes):,} nodes and {len(graph.edges):,} edges")
    return graph


def build_networkx_graph(device_graph: DeviceGraph) -> nx.DiGraph:
    """Convert DeviceGraph to NetworkX DiGraph."""
    print("Building NetworkX graph...")
    G = nx.DiGraph()

    for k_num, node in device_graph.nodes.items():
        G.add_node(k_num, **node.model_dump())

    valid_nodes = set(device_graph.nodes.keys())
    for edge in device_graph.edges:
        if edge.source in valid_nodes and edge.target in valid_nodes:
            G.add_edge(edge.source, edge.target)

    print(
        f"  NetworkX graph: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges"
    )
    return G


def extract_year_from_k_number(k_number: str) -> int | None:
    """Extract year from K-number format."""
    match = re.match(r"[Kk](\d{2})", k_number)
    if not match:
        return None
    yy = int(match.group(1))
    return 1900 + yy if yy >= 76 else 2000 + yy


def parse_decision_date(date_str: str | None) -> int | None:
    """Extract year from decision_date field."""
    if not date_str:
        return None
    try:
        return int(date_str[:4])
    except (ValueError, IndexError):
        return None


def compute_graph_statistics(G: nx.DiGraph) -> GraphStatistics:
    """Compute basic graph metrics."""
    print("Computing graph statistics...")

    in_degrees = [d for _, d in G.in_degree()]
    out_degrees = [d for _, d in G.out_degree()]

    wccs = list(nx.weakly_connected_components(G))
    largest_wcc_size = max(len(c) for c in wccs) if wccs else 0

    root_nodes = [n for n in G.nodes() if G.in_degree(n) == 0]
    leaf_nodes = [n for n in G.nodes() if G.out_degree(n) == 0]

    stats = GraphStatistics(
        total_nodes=G.number_of_nodes(),
        total_edges=G.number_of_edges(),
        density=nx.density(G),
        num_weakly_connected_components=len(wccs),
        largest_wcc_size=largest_wcc_size,
        num_root_nodes=len(root_nodes),
        num_leaf_nodes=len(leaf_nodes),
        avg_in_degree=sum(in_degrees) / len(in_degrees) if in_degrees else 0,
        avg_out_degree=sum(out_degrees) / len(out_degrees) if out_degrees else 0,
        max_in_degree=max(in_degrees) if in_degrees else 0,
        max_out_degree=max(out_degrees) if out_degrees else 0,
    )

    print(f"  Density: {stats.density:.6f}")
    print(f"  Connected components: {stats.num_weakly_connected_components:,}")
    print(f"  Root nodes: {stats.num_root_nodes:,}")
    print(f"  Max in-degree: {stats.max_in_degree}")

    return stats


def find_root_nodes(G: nx.DiGraph) -> list[str]:
    """Find devices with no predecessors (in_degree = 0)."""
    return [n for n in G.nodes() if G.in_degree(n) == 0]


def find_most_cited_devices(G: nx.DiGraph, top_n: int = 50) -> list[DeviceMetrics]:
    """Find devices with highest in-degree (most frequently used as predicates)."""
    print(f"Finding top {top_n} most-cited devices...")

    in_degrees = [(n, G.in_degree(n), G.out_degree(n)) for n in G.nodes()]
    in_degrees.sort(key=lambda x: x[1], reverse=True)

    results = []
    for node_id, in_deg, out_deg in in_degrees[:top_n]:
        node_data = G.nodes[node_id]
        results.append(
            DeviceMetrics(
                device_id=node_id,
                in_degree=in_deg,
                out_degree=out_deg,
                applicant=node_data.get("applicant", "Unknown"),
                device_name=node_data.get("device_name", "Unknown"),
            )
        )

    print(f"  Top device: {results[0].device_id} with {results[0].in_degree} citations")
    return results


def _find_longest_path_from_node(args: tuple[nx.DiGraph, str]) -> list[str]:
    """Find longest path starting from a given node (worker function)."""
    G, start_node = args
    longest = [start_node]

    def dfs(node: str, path: list[str]) -> list[str]:
        nonlocal longest
        successors = list(G.successors(node))
        if not successors:
            if len(path) > len(longest):
                longest = path[:]
            return path

        for succ in successors:
            if succ not in path:
                dfs(succ, path + [succ])

        if len(path) > len(longest):
            longest = path[:]
        return longest

    dfs(start_node, [start_node])
    return longest


def find_longest_chains(G: nx.DiGraph, top_n: int = 20) -> list[ChainInfo]:
    """Find the longest predicate chains using DFS from root nodes."""
    print(f"Finding top {top_n} longest chains...")

    root_nodes = find_root_nodes(G)
    print(f"  Searching from {len(root_nodes):,} root nodes...")

    all_chains: list[list[str]] = []

    for root in tqdm(root_nodes, desc="Finding chains"):
        chain = _find_longest_path_from_node((G, root))
        if len(chain) > 1:
            all_chains.append(chain)

    all_chains.sort(key=len, reverse=True)

    results = []
    for chain in all_chains[:top_n]:
        start_year = None
        end_year = None

        start_data = G.nodes.get(chain[0], {})
        end_data = G.nodes.get(chain[-1], {})

        start_year = parse_decision_date(start_data.get("decision_date"))
        if not start_year:
            start_year = extract_year_from_k_number(chain[0])

        end_year = parse_decision_date(end_data.get("decision_date"))
        if not end_year:
            end_year = extract_year_from_k_number(chain[-1])

        span_years = None
        if start_year and end_year:
            span_years = end_year - start_year

        results.append(
            ChainInfo(
                chain=chain,
                length=len(chain),
                start_device=chain[0],
                end_device=chain[-1],
                start_year=start_year,
                end_year=end_year,
                span_years=span_years,
            )
        )

    if results:
        print(
            f"  Longest chain: {results[0].length} devices spanning {results[0].span_years} years"
        )

    return results


def normalize_company_name(name: str) -> str:
    """Normalize company names to handle variations."""
    name = name.upper().strip()
    suffixes = [
        ", INC.",
        ", INC",
        " INC.",
        " INC",
        ", LLC",
        " LLC",
        ", L.L.C.",
        ", CORP.",
        ", CORP",
        " CORP.",
        " CORP",
        ", CO.",
        ", CO",
        " CO.",
        ", LTD.",
        ", LTD",
        " LTD.",
        " LTD",
        ", LIMITED",
        " LIMITED",
        ", L.P.",
        " L.P.",
        ", LP",
        " LP",
    ]
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name.strip()


def compute_company_metrics(G: nx.DiGraph, top_n: int = 50) -> list[CompanyMetrics]:
    """Compute per-company statistics."""
    print(f"Computing company metrics...")

    company_devices: dict[str, list[str]] = defaultdict(list)
    for node_id in G.nodes():
        applicant = G.nodes[node_id].get("applicant", "Unknown")
        normalized = normalize_company_name(applicant)
        company_devices[normalized].append(node_id)

    print(f"  Found {len(company_devices):,} unique companies")

    results = []
    for company, devices in tqdm(
        company_devices.items(), desc="Computing company metrics"
    ):
        device_set = set(devices)

        devices_as_predicates = 0
        total_citations = 0
        for device_id in devices:
            in_deg = G.in_degree(device_id)
            if in_deg > 0:
                devices_as_predicates += 1
                total_citations += in_deg

        unique_predicates = set()
        cross_company_count = 0
        for device_id in devices:
            for pred in G.successors(device_id):
                unique_predicates.add(pred)
                pred_company = normalize_company_name(
                    G.nodes[pred].get("applicant", "Unknown")
                )
                if pred_company != company:
                    cross_company_count += 1

        total_preds = len(unique_predicates)
        ratio = cross_company_count / total_preds if total_preds > 0 else 0.0

        results.append(
            CompanyMetrics(
                name=company,
                total_devices=len(devices),
                devices_as_predicates=devices_as_predicates,
                total_predicate_citations=total_citations,
                unique_predicates_used=total_preds,
                cross_company_predicate_count=cross_company_count,
                cross_company_predicate_ratio=ratio,
            )
        )

    results.sort(key=lambda x: x.total_predicate_citations, reverse=True)
    top_results = results[:top_n]

    if top_results:
        print(
            f"  Top company: {top_results[0].name} with {top_results[0].total_predicate_citations} citations"
        )

    return top_results


def build_company_network(
    G: nx.DiGraph, min_edge_count: int = 5
) -> list[CompanyRelationship]:
    """Build company-to-company predicate network."""
    print(f"Building company network (min edges: {min_edge_count})...")

    edge_counts: dict[tuple[str, str], int] = defaultdict(int)

    for source, target in tqdm(
        G.edges(), desc="Processing edges", total=G.number_of_edges()
    ):
        source_company = normalize_company_name(
            G.nodes[source].get("applicant", "Unknown")
        )
        target_company = normalize_company_name(
            G.nodes[target].get("applicant", "Unknown")
        )

        if source_company != target_company:
            edge_counts[(source_company, target_company)] += 1

    results = []
    for (source, target), count in edge_counts.items():
        if count >= min_edge_count:
            results.append(
                CompanyRelationship(
                    source_company=source,
                    target_company=target,
                    edge_count=count,
                )
            )

    results.sort(key=lambda x: x.edge_count, reverse=True)
    print(f"  Found {len(results):,} company relationships (>= {min_edge_count} edges)")

    return results


def contact_leaderboard(G: nx.DiGraph):
    """Compute the contact leaderboard."""
    print("Computing contact leaderboard...")

    contacts = defaultdict(int)
    for node_id in G.nodes():
        contact = G.nodes[node_id].get("contact", "Unknown")
        contacts[contact] += 1

    contacts = sorted(contacts.items(), key=lambda x: x[1], reverse=True)

    for contact, count in contacts[:10]:
        print(f"  {contact}: {count} contacts")

    return contacts


def run_analysis(
    graph_path: Path = GRAPH_PATH,
    output_path: Path = DATA_PATH / "analysis.json",
    top_n_chains: int = 20,
    top_n_devices: int = 50,
    top_n_companies: int = 50,
    min_company_edges: int = 5,
) -> AnalysisResults:
    """Run full analysis pipeline with progress output."""
    print("=" * 60)
    print("Medical Device Graph Analysis")
    print("=" * 60)

    device_graph = load_device_graph(graph_path)
    G = build_networkx_graph(device_graph)

    graph_stats = compute_graph_statistics(G)
    most_cited = find_most_cited_devices(G, top_n_devices)
    root_nodes = find_root_nodes(G)
    longest_chains = (None,)  # find_longest_chains(G, top_n_chains)
    top_companies = compute_company_metrics(G, top_n_companies)
    company_network = build_company_network(G, min_company_edges)
    contact_leaderboard(G)

    #    lp = nx.dag_longest_path(G)
    # identify cycles in the graph
    cycles = list(nx.simple_cycles(G))
    print(f"  Found {len(cycles):,} cycles in the graph")
    for cycle in cycles:
        print(f"  {cycle}")

    results = AnalysisResults(
        generated_at=datetime.now(timezone.utc).isoformat(),
        graph_stats=graph_stats,
        longest_chains=longest_chains,
        most_cited_devices=most_cited,
        root_nodes=root_nodes[:1000],
        top_companies=top_companies,
        company_network=company_network,
    )

    print(f"\nWriting results to {output_path}...")
    with open(output_path, "w") as f:
        json.dump(results.model_dump(), f, indent=2)
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"  Size: {size_mb:.2f} MB")

    print("\n" + "=" * 60)
    print("Analysis Complete")
    print("=" * 60)

    return results


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze medical device predicate graph"
    )
    parser.add_argument(
        "--graph", type=Path, default=GRAPH_PATH, help="Path to graph.json"
    )
    parser.add_argument(
        "--output", type=Path, default=DATA_PATH / "analysis.json", help="Output path"
    )
    parser.add_argument(
        "--top-chains", type=int, default=1, help="Number of longest chains to find"
    )
    parser.add_argument(
        "--top-devices", type=int, default=50, help="Number of top devices to return"
    )
    parser.add_argument(
        "--top-companies",
        type=int,
        default=50,
        help="Number of top companies to return",
    )
    parser.add_argument(
        "--min-company-edges",
        type=int,
        default=5,
        help="Minimum edges for company network",
    )

    args = parser.parse_args()

    run_analysis(
        graph_path=args.graph,
        output_path=args.output,
        top_n_chains=args.top_chains,
        top_n_devices=args.top_devices,
        top_n_companies=args.top_companies,
        min_company_edges=args.min_company_edges,
    )


if __name__ == "__main__":
    main()
