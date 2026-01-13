# Data Pipeline

I use a basic set of scripts for converting FDA 510k data into a graph.

Key pieces are:

`download.py`: Download PDFs from the FDA. If they we have it locally or we know the pdf summary does not exist
do not download it again! Respect the FDA limits. Uses `data/pdf.json` to keep track of what pdfs we know
do not exist.

`textify.py`: Extract text from the PDFs. Extraction is quick and can be rerun quickly. Rerun each time but
use `data/text.json` to keep track of what devices have had text extracted using AI/OCR. We do not want to 
override that.

`extract.py`: Extract predicates from the text. This is done using quick regex matching. The predicate results
are merged with `data/predicate_overrides.json` to allow for manual overrides (there are many cases where the regex
is not perfect).

`graph.py`: Build the graph. This is done using the predicates and the aggregate predicates.


# Assembling the predicates

Extracting the predicates is not as easy as regex matching.

- Some device summaries are scanned documents and do not have embedded text
- Some device summaries have text but the predicate IDs are not formatted properly (eg. K1 00218 or ki00218)
- Some device summaries have text but the predicate IDs are not present at all
- Some device summaries reference many devices but only a subset are predicates
- Some devices have text but the predicate ids are present in an image or other non-textual format

I am ussing an aggregate approach to extract the predicates. I generate a list of predicates for each device using the following methods:

- Use regex + rawtext
- Use claudecode
- Use human overrides

I then merge the predicates together and remove duplicates. Human > claude > regex.

The ClaudeCode approach is nice because:
- I already pay for it
- It is able to process PDFS (both the text and as images!). It properly extracted predicates from images for K252870.

I've explored a few other ideas:

- Use Ollama + local vision model (gemma, ministral) to extract text from PDF images and then predicates. This takes longer than I'd 
- Use Mistral's OCR model to extract text from PDFs at 1000pages/$1
- Feed the fulltext to an LLM and extract the predicates


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