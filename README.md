# devtree

![Devtree](frontend/public/devtree.png)

## Overview

Devtree is a tool for exploring the device tree of medical devices in the USA. 

### Background

Medical devices in the USA are approved through different pathways. The most common pathway is the 510(k).
This pathway allows companies to to prove their device is substantially equivalent to a previously approved.
By doing so, they avoid the more rigorous approval processes. This is because the regulatory body is already
aware of the device and its safety and effectiveness. Devices may still be different but it helps decrease
the surface area for review.

The FDA publishes 510k device summaries on their [website](https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpub/applica.cfm).
From the PDF summaries, the predicate information can be extracted and stored.

### Technical Overview

The core data pipeline is:
- Download the 510k device dataset
- For each device, download the PDF summary
- Extract the text from the PDFs using the embedded text and/or OCR 
- Extract the device -> predicate relationships

The frontend exposes this data as a graph and lets you explore the device tree.


## Running the data pipeline

These assume PDF files are located in `pdfs` and text files are located in `device_text`.


```bash
# Copy down existing data files
gsutil -m rsync gs://devtree/pdfs pdfs
gsutil -m rsync gs://devtree/data/*.json

# Download new PDFS
uv run code/pipeline/download.py

# Extract text from the PDFs
uv run code/pipeline/textify.py

# Extract predicates from the text using regex + pymupdf
uv run code/pipeline/extract.py

# Optional: Use claude code / other tooling to extract predicates for additional devices
claude "Please identify interesting predicates and extract their predicates"

# Build graph
uv run code/pipeline/graph.py


# Sync back up to GCS
gsutil -m rsync pdfs gs://devtree/pdfs

for file in data/predicates_*.json; do
    gsutil rsync $file gs://devtree/data/
done
```


## Running the Frontend (Development)

Requires Node.js 20+. If using nvm:

```bash
source ~/.nvm/nvm.sh && nvm use 20
cd frontend
npm run dev
```

The app will be available at http://localhost:3000

## Building and Serving Static Site

To build the static site for production:

```bash
source ~/.nvm/nvm.sh && nvm use 20
cd frontend
npm run build
```

This generates a static site in the `frontend/out/` directory. Copy to `docs`.

To serve the static site locally:

```bash
npx serve out -p 3001
```

The static site will be available at http://localhost:3001

