# FDA Device Predicate Graph Project

## Overview
Building a graph of FDA medical device predicate relationships from 510(k) clearance data.

## Background
- The FDA's 510(k) pathway allows devices to be cleared by demonstrating "substantial equivalence" to a predicate device
- This creates a directed graph where edges represent predicate relationships
- Some device lineages trace back to devices from the 1970s

## Goals
- [ ] Acquire 510(k) clearance data with predicate information
- [ ] Parse and structure the data
- [ ] Build a graph data structure
- [ ] Visualize the predicate network
- [ ] Enable interesting queries and analysis

## Data Sources Research (2025-12-30)

- You can download the 510k data from https://open.fda.gov/data/downloads/ / https://download.open.fda.gov/device/510k/device-510k-0001-of-0001.json.zip
- This contains metadata about all 510k devices.
- It looks like each file has a URL like `https://www.accessdata.fda.gov/cdrh_docs/pdf15/K152289.pdf` that defines the summary of the device. Using the year or prefix of the 510k number, we can get the PDF.

## extracting predicates from the pdfs


## ideas

- make a leaderboard of people who have submitted with the most devices
- make an interface that lets people ask a query and get an answer