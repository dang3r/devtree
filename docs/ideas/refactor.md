# Refactoring idea

### key data files

- pdfs has all pdfs (not persisted in the repo)
- text has all text (persisted in the repo)
- data/
    - data/db.json: This has this structure:
    - ```json
    {
        "devices": {
            "K120828": {
                "predicates": [ "K100218", "K100219", "K100220" ],
                "human_verified": true/false,
                "pdf_present": true/false,
                "errors": {
                }
            }
        }
    }
    ```
    - device_graph.json: The core structure with all metadata
    - cytoscape.json: The cytoscape json file for the device graph



# Pipeline
- download the fda json file from the fda website
- compare the device numbers in that with the device numbers in the db.json file
- determine what devices to process:
    - if the device is new, process it.
    - if the device is in the db.json file, the pdf is present, and that device is from the last 2 months, process it. THis should not be many devices
- for each device:
    - download pdf:
        - if not present, return result with pdf_present: false and other details
        - if present: download
    - extract predicates:
        - path1:
            - if text is present within the pdf: use pymupdf to extract the text.
            - save text to text/
            - run a regex to extract the predicates
            - if predicates are found generate result
        - path2: no predicates found with path1
            - use ollama + local model to extract text from the pdf
            - save text to text/
            - use regex to extract predicates
            - FUTURE_NOTE: if lightweight enough, use llms to extract all predicates
        - 
