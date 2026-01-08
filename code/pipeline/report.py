"""
Generate PR description for weekly sync.

Creates a markdown report summarizing new devices, flagged cases, and pipeline stats.
"""

from datetime import datetime, timezone

from pydantic import BaseModel

from .download import DownloadSummary
from .extract import ExtractionResult, ExtractionSummary
from .fetch import FetchResult


class PipelineStats(BaseModel):
    """Overall pipeline execution stats."""

    started_at: str
    completed_at: str
    duration_seconds: float


def format_duration(seconds: float) -> str:
    """Format duration as human-readable string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}m {secs}s"


def generate_report(
    fetch_result: FetchResult,
    download_summary: DownloadSummary,
    extraction_results: list[ExtractionResult],
    extraction_summary: ExtractionSummary,
    fda_data: dict,
    stats: PipelineStats,
) -> str:
    """Generate PR description markdown."""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Build device lookup for metadata
    device_lookup = {
        d.get("k_number"): d
        for d in fda_data.get("results", [])
    }

    lines = [
        f"## Weekly Device Sync - {date_str}",
        "",
        "### Summary",
        f"- **New devices processed**: {fetch_result.new_count}",
        f"- **PDFs downloaded**: {download_summary.success} ({download_summary.failed} unavailable)",
        f"- **Predicates extracted**: {extraction_summary.with_predicates} devices with predicates",
        f"- **Flagged for review**: {extraction_summary.flagged} devices",
        "",
    ]

    # New devices table (limit to 50 for readability)
    if extraction_results:
        lines.extend([
            "### New Devices",
            "",
            "| K-Number | Applicant | Device Name | Predicates |",
            "|----------|-----------|-------------|------------|",
        ])

        for result in extraction_results[:50]:
            device = device_lookup.get(result.k_number, {})
            applicant = device.get("applicant", "Unknown")[:30]
            name = device.get("device_name", "Unknown")[:40]
            preds = ", ".join(result.predicates.predicates[:3])
            if len(result.predicates.predicates) > 3:
                preds += f" (+{len(result.predicates.predicates) - 3} more)"

            lines.append(f"| {result.k_number} | {applicant} | {name} | {preds} |")

        if len(extraction_results) > 50:
            lines.append(f"| ... | *{len(extraction_results) - 50} more devices* | | |")

        lines.append("")

    # Flagged cases
    flagged = [r for r in extraction_results if r.flags]
    if flagged:
        lines.extend([
            "### Flagged Cases",
            "",
        ])

        for result in flagged[:20]:
            device = device_lookup.get(result.k_number, {})
            name = device.get("device_name", "Unknown")

            for flag in result.flags:
                reason_display = flag.reason.replace("_", " ").title()
                lines.extend([
                    f"#### {result.k_number} - {reason_display}",
                    f"**Device**: {name}",
                    f"**Details**: {flag.details}",
                    "",
                ])

        if len(flagged) > 20:
            lines.append(f"*... and {len(flagged) - 20} more flagged devices*")
            lines.append("")

    # Failed downloads
    failed_downloads = [r for r in download_summary.results if r.status == "failed"]
    if failed_downloads:
        lines.extend([
            "### Failed Downloads",
            "",
        ])
        for result in failed_downloads[:10]:
            lines.append(f"- **{result.k_number}**: {result.error}")
        if len(failed_downloads) > 10:
            lines.append(f"- *... and {len(failed_downloads) - 10} more*")
        lines.append("")

    # Pipeline stats
    lines.extend([
        "### Pipeline Stats",
        f"- **Runtime**: {format_duration(stats.duration_seconds)}",
        f"- **Total in FDA dataset**: {fetch_result.total_in_new:,}",
        "",
    ])

    return "\n".join(lines)


def generate_report_file(
    fetch_result: FetchResult,
    download_summary: DownloadSummary,
    extraction_results: list[ExtractionResult],
    extraction_summary: ExtractionSummary,
    fda_data: dict,
    stats: PipelineStats,
    output_path: str,
) -> str:
    """Generate report and save to file. Returns the markdown content."""
    content = generate_report(
        fetch_result,
        download_summary,
        extraction_results,
        extraction_summary,
        fda_data,
        stats,
    )

    with open(output_path, "w") as f:
        f.write(content)

    return content
