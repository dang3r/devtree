#!/usr/bin/env python3
"""
Cluster similar company names and generate a mapping file for normalization.

Aggressive strategy:
- Strip corporate suffixes (Inc, Corp, LLC, etc.)
- Extract parent company names from divisions (e.g., "Medtronic Vascular" → "Medtronic")
- Group variations by common prefix
- Output mapping file for human review
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

# Corporate suffixes to strip (order matters - longer first)
SUFFIXES = [
    r",?\s*incorporated",
    r",?\s*corporation",
    r",?\s*company",
    r",?\s*limited",
    r",?\s*l\.?l\.?c\.?",
    r",?\s*l\.?l\.?p\.?",
    r",?\s*inc\.?",
    r",?\s*corp\.?",
    r",?\s*ltd\.?",
    r",?\s*co\.?",
    r",?\s*plc\.?",
    r",?\s*gmbh",
    r",?\s*s\.?a\.?s\.?",
    r",?\s*s\.?a\.?",
    r",?\s*b\.?v\.?",
    r",?\s*n\.?v\.?",
    r",?\s*a\.?g\.?",
    r",?\s*a/s",
]

# Build regex pattern for suffix removal
SUFFIX_PATTERN = re.compile(
    r"(" + "|".join(SUFFIXES) + r")\s*$",
    re.IGNORECASE,
)


def normalize_name(name: str) -> str:
    """Normalize a company name for clustering."""
    # Lowercase
    normalized = name.lower().strip()

    # Remove parenthetical content like "(USA)" or "(formerly XYZ)"
    normalized = re.sub(r"\([^)]*\)", "", normalized)

    # Strip corporate suffixes
    normalized = SUFFIX_PATTERN.sub("", normalized)

    # Remove trailing punctuation and whitespace
    normalized = re.sub(r"[,.\s]+$", "", normalized)

    # Normalize whitespace
    normalized = re.sub(r"\s+", " ", normalized).strip()

    return normalized


def extract_parent_name(normalized: str, known_parents: set[str]) -> str | None:
    """
    Extract parent company name if this looks like a division.
    Returns the parent name if found, None otherwise.
    Checks longer matches first (two-word before one-word).
    """
    words = normalized.split()
    if len(words) < 2:
        return None

    # Check longer matches first (two-word parents like "boston scientific")
    for i in range(min(len(words) - 1, 3), 0, -1):
        candidate = " ".join(words[:i])
        if candidate in known_parents:
            # Make sure this isn't the full name (avoid self-mapping)
            if candidate != normalized:
                return candidate

    return None


# Common words that should NOT be treated as parent companies
COMMON_WORDS = {
    "american", "medical", "the", "general", "national", "international",
    "advanced", "united", "precision", "global", "bio", "diagnostic",
    "health", "healthcare", "surgical", "clinical", "digital", "electronic",
    "applied", "professional", "scientific", "shenzhen", "shanghai", "beijing",
    "guangzhou", "hangzhou", "suzhou", "jiangsu", "zhejiang", "new", "first",
}


def find_parent_companies(
    name_counts: Counter[str],
    min_variants: int = 5,
    min_devices: int = 200,
) -> set[str]:
    """
    Find company names that appear to be parents with divisions.
    More conservative - only identifies clear parent companies.
    Handles both single-word and two-word parent names.
    """
    # Normalize all names once
    normalized_names: dict[str, str] = {}
    for name in name_counts:
        normalized_names[name] = normalize_name(name)

    # Group by first word
    first_word_groups: dict[str, list[tuple[str, str, int]]] = defaultdict(list)
    for name, count in name_counts.items():
        normalized = normalized_names[name]
        if not normalized:
            continue
        first_word = normalized.split()[0] if normalized.split() else ""
        if first_word and first_word not in COMMON_WORDS:
            first_word_groups[first_word].append((name, normalized, count))

    parents = set()

    for first_word, names in first_word_groups.items():
        if len(first_word) < 4:
            continue

        # Check for single-word parent
        unique_normalized = set(n for _, n, _ in names)
        total_devices = sum(c for _, _, c in names)

        if first_word in unique_normalized:
            if len(unique_normalized) >= min_variants and total_devices >= min_devices:
                parents.add(first_word)

        # Check for two-word parents (e.g., "boston scientific")
        two_word_groups: dict[str, list[tuple[str, str, int]]] = defaultdict(list)
        for orig, norm, count in names:
            words = norm.split()
            if len(words) >= 2:
                two_word = " ".join(words[:2])
                two_word_groups[two_word].append((orig, norm, count))

        for two_word, tw_names in two_word_groups.items():
            tw_unique = set(n for _, n, _ in tw_names)
            tw_devices = sum(c for _, _, c in tw_names)

            # Check if two-word name exists as standalone AND has divisions
            if two_word in tw_unique and len(tw_unique) >= 3 and tw_devices >= 100:
                parents.add(two_word)

    return parents


def cluster_companies(name_counts: Counter[str]) -> dict[str, list[str]]:
    """
    Cluster company names into canonical groups.
    Returns: {canonical_name: [original_name1, original_name2, ...]}
    """
    # First pass: find parent companies
    parents = find_parent_companies(name_counts)
    print(f"Found {len(parents)} parent company prefixes")

    # Second pass: group all names
    clusters: dict[str, list[str]] = defaultdict(list)

    for original_name, count in name_counts.items():
        normalized = normalize_name(original_name)
        if not normalized:
            clusters["Unknown"].append(original_name)
            continue

        # Check if this is a division of a known parent
        parent = extract_parent_name(normalized, parents)

        if parent:
            # Use parent as canonical name (title case)
            canonical = parent.title()
        else:
            # Use normalized name as canonical (title case)
            canonical = normalized.title()

        clusters[canonical].append(original_name)

    # Sort variants by device count (descending) within each cluster
    for canonical in clusters:
        clusters[canonical].sort(key=lambda x: -name_counts.get(x, 0))

    return dict(clusters)


def filter_clusters(
    clusters: dict[str, list[str]],
    name_counts: Counter[str],
    min_variants: int = 2,
) -> dict[str, list[str]]:
    """
    Filter clusters to only include those with multiple variants.
    Single-variant clusters don't need mapping.
    """
    filtered = {}
    for canonical, variants in clusters.items():
        if len(variants) >= min_variants:
            filtered[canonical] = variants
        elif len(variants) == 1:
            # Single variant - only include if canonical differs from original
            original = variants[0]
            if original != canonical:
                filtered[canonical] = variants

    return filtered


def load_fda_data(path: Path) -> Counter[str]:
    """Load FDA data and count applicant names."""
    print(f"Loading FDA data from {path}...")
    with open(path) as f:
        data = json.load(f)

    counts: Counter[str] = Counter()
    for device in data["results"]:
        applicant = device.get("applicant", "Unknown")
        counts[applicant] += 1

    print(f"  Found {len(counts):,} unique applicant names")
    print(f"  Total devices: {sum(counts.values()):,}")
    return counts


def main() -> None:
    project_root = Path(__file__).parent.parent
    data_path = project_root / "data"

    # Load applicant counts
    name_counts = load_fda_data(data_path / "device-510k-0001-of-0001.json")

    # Cluster companies
    print("\nClustering companies...")
    clusters = cluster_companies(name_counts)
    print(f"  Created {len(clusters):,} clusters")

    # Filter to only meaningful mappings
    print("\nFiltering clusters...")
    filtered = filter_clusters(clusters, name_counts)
    print(f"  {len(filtered):,} clusters with mappings")

    # Calculate stats
    total_mapped = sum(len(v) for v in filtered.values())
    total_devices_mapped = sum(
        name_counts[name] for variants in filtered.values() for name in variants
    )

    print(f"\n=== Mapping Statistics ===")
    print(f"Canonical companies: {len(filtered):,}")
    print(f"Original names mapped: {total_mapped:,}")
    print(f"Devices affected: {total_devices_mapped:,}")

    # Show top clusters by device count
    print(f"\n=== Top 20 Clusters by Device Count ===")
    cluster_device_counts = [
        (canonical, sum(name_counts[n] for n in variants), len(variants))
        for canonical, variants in filtered.items()
    ]
    cluster_device_counts.sort(key=lambda x: -x[1])

    for canonical, device_count, variant_count in cluster_device_counts[:20]:
        print(f"  {device_count:5,} devices  {variant_count:3} variants  {canonical}")

    # Write output
    output_path = data_path / "company_mappings.json"
    print(f"\nWriting mappings to {output_path}...")

    # Sort by device count for easier review
    sorted_clusters = dict(
        sorted(
            filtered.items(),
            key=lambda x: -sum(name_counts[n] for n in x[1])
        )
    )

    with open(output_path, "w") as f:
        json.dump(sorted_clusters, f, indent=2)

    print("Done!")


if __name__ == "__main__":
    main()
