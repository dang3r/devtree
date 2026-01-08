"""
DevTree Data Pipeline

Autonomous pipeline for processing FDA 510(k) device data.
Designed to run in CI (GitHub Actions) on a weekly schedule.
"""

from .db import (
    DeviceDatabase,
    DeviceEntry,
    DeviceErrors,
    load_db,
    save_db,
    get_devices_needing_processing,
    update_device_from_download,
    update_device_from_extraction,
    set_human_verified,
)
from .download import download_pdfs, DownloadSummary
from .extract import extract_all, ExtractionResult, ExtractionSummary
from .fetch import fetch_and_diff, fetch_and_diff_with_db, FetchResult
from .graph import build_graph, export_graph, export_cytoscape, DeviceGraph
from .report import generate_report, generate_report_file, PipelineStats

__all__ = [
    # Database
    "DeviceDatabase",
    "DeviceEntry",
    "DeviceErrors",
    "load_db",
    "save_db",
    "get_devices_needing_processing",
    "update_device_from_download",
    "update_device_from_extraction",
    "set_human_verified",
    # Fetch
    "fetch_and_diff",
    "fetch_and_diff_with_db",
    "FetchResult",
    # Download
    "download_pdfs",
    "DownloadSummary",
    # Extract
    "extract_all",
    "ExtractionResult",
    "ExtractionSummary",
    # Graph
    "build_graph",
    "export_graph",
    "export_cytoscape",
    "DeviceGraph",
    # Report
    "generate_report",
    "generate_report_file",
    "PipelineStats",
]
