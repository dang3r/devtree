# Data Files

- You can download the 510k data from https://open.fda.gov/data/downloads/ / https://download.open.fda.gov/device/510k/device-510k-0001-of-0001.json.zip

- The core internal data files I use are:
- - data/
    - devices.json: Keeps track of PDF, text, and predicate information for each device.
    - predicates.json: Keeps track of the predicate information for each predicate. Committed to the repo
    - cytoscape.json: The cytoscape.js JSON file for the graph. Committed to the repo
- pdfs/
    - Device PDF files. Not all devices have PDF summaries
- text/
    - The text of the PDF summaries. Retrieved using the embedded text and/or OCR.