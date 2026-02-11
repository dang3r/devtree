# Devtree Agent Guide

This document is the canonical guide for how automation and data updates work in this repo.

## Overview

Devtree builds a predicate graph from FDA 510(k) device summaries. A weekly GitHub Action runs the pipeline,
publishes updated predicate data to the private bucket, and uploads the latest graph to the public bucket
for the site to consume.

## Weekly Automation

The weekly sync is run by the GitHub Action:
- Workflow: `.github/workflows/weekly-sync.yml`
- Script: `scripts/weekly_sync.sh`

### What the weekly job does

1. Pulls the latest `data/gt/predicates.json` from the private bucket:
   - `r2:devtree-private/gt/predicates.json` → `data/gt/predicates.json`
2. Runs the pipeline for new devices:
   - `uv run code/pipeline/pipeline.py new`
3. Copies the latest predicates into `data/gt/predicates.json`:
   - `jobs/<timestamp>/final_predicates.json` → `data/gt/predicates.json`
4. Uploads updated predicates back to the private bucket:
   - `data/gt/predicates.json` → `r2:devtree-private/gt/predicates.json`
5. Uploads the latest public graph to the public bucket:
   - `jobs/<timestamp>/cytoscape.json.gz` → `r2:devtree/cytoscape_graph.json.gz`

### Required GitHub Actions secrets

- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_ENDPOINT`
- `OPENROUTER_API_KEY`

### Local usage

Run the full weekly job locally:
```bash
scripts/weekly_sync.sh
```

Dry run (no downloads/uploads/pipeline execution):
```bash
scripts/weekly_sync.sh --dry-run
```

## Public Graph URL

The site loads the public graph file from:
`https://data.devtree.ca/cytoscape_graph.json.gz`

The upload step sets metadata so browsers handle the gzip correctly:
- `content-type: application/json`
- `content-encoding: gzip`

## Notes

- The weekly job does not download old PDFs or text files.
- Historical predicate data is persisted via `data/gt/predicates.json` in `devtree-private`.
- The frontend does not require a rebuild for new data; it fetches the public URL directly.
