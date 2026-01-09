# devtree

![Devtree](docs/devtree.png)

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

