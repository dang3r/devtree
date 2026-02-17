#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DRY_RUN="false"
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN="true"
fi

# Load local env if present (for local runs).
if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

echo "Starting weekly sync (dry_run=${DRY_RUN})"

# R2 config (uses env vars provided by GitHub Actions secrets)
export RCLONE_CONFIG_R2_PROVIDER="Cloudflare"
export RCLONE_CONFIG_R2_TYPE="s3"
export RCLONE_CONFIG_R2_ACCESS_KEY_ID="${R2_ACCESS_KEY_ID:-}"
export RCLONE_CONFIG_R2_SECRET_ACCESS_KEY="${R2_SECRET_ACCESS_KEY:-}"
export RCLONE_CONFIG_R2_ENDPOINT="${R2_ENDPOINT:-}"

if [[ -z "${RCLONE_CONFIG_R2_ACCESS_KEY_ID}" || -z "${RCLONE_CONFIG_R2_SECRET_ACCESS_KEY}" || -z "${RCLONE_CONFIG_R2_ENDPOINT}" ]]; then
  echo "Missing R2 credentials. Ensure R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, and R2_ENDPOINT are set."
  exit 1
fi

if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
  echo "Missing OPENROUTER_API_KEY."
  exit 1
fi

echo "Syncing existing predicates from devtree-private..."
if [[ "${DRY_RUN}" == "false" ]]; then
  mkdir -p data/gt
  rclone copyto r2:devtree-private/gt/predicates.json data/gt/predicates.json || true
  if [[ ! -f "data/gt/predicates.json" ]]; then
    echo "Missing data/gt/predicates.json after download."
    exit 1
  fi
  # sync pdf.json from remote
  rclone copyto r2:devtree-private/pdf.json data/pdf.json || true
else
  echo "Dry run: skipping predicates download"
fi

echo "Running pipeline for new devices..."
if [[ "${DRY_RUN}" == "false" ]]; then
  uv run code/pipeline/pipeline.py new
else
  echo "Dry run: skipping pipeline execution"
fi

LATEST_JOB_DIR=""
if [[ -d "jobs" ]]; then
  LATEST_JOB_DIR="$(ls -td jobs/* | head -n 1 || true)"
fi

if [[ -z "${LATEST_JOB_DIR}" ]]; then
  echo "No jobs directory found. Nothing to upload."
  exit 1
fi

echo "Latest job dir: ${LATEST_JOB_DIR}"

if [[ "${DRY_RUN}" == "false" ]]; then
  if [[ -f "${LATEST_JOB_DIR}/final_predicates.json" ]]; then
    cp "${LATEST_JOB_DIR}/final_predicates.json" data/gt/predicates.json
  else
    echo "Missing ${LATEST_JOB_DIR}/final_predicates.json"
    exit 1
  fi

  echo "Uploading predicates.json to devtree-private..."
  rclone copyto data/gt/predicates.json r2:devtree-private/gt/predicates.json

  echo "Uploading new PDFs and text to devtree-private..."
  find pdfs -type f -mtime -1 -print > /tmp/new_pdfs.txt
  find text -type f -mtime -1 -print > /tmp/new_text.txt
  rclone copy pdfs r2:devtree-private/pdfs --files-from /tmp/new_pdfs.txt --fast-list --transfers 16 --checkers 32
  rclone copy text r2:devtree-private/text --files-from /tmp/new_text.txt --fast-list --transfers 16 --checkers 32

  echo "Uploading cytoscape.json.gz to public devtree bucket..."
  if [[ ! -f "${LATEST_JOB_DIR}/cytoscape.json.gz" ]]; then
    echo "Missing ${LATEST_JOB_DIR}/cytoscape.json.gz"
    exit 1
  fi

  rclone copyto \
    --metadata-set "content-type=application/json" \
    --metadata-set "content-encoding=gzip" \
    "${LATEST_JOB_DIR}/cytoscape.json.gz" \
    r2:devtree/cytoscape_graph.json.gz
else
  echo "Dry run: skipping uploads"
fi

echo "Weekly sync complete."
