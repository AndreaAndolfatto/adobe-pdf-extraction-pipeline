# Adobe PDF Extraction Pipeline

A three-stage Python pipeline for extracting, merging, and filtering text from PDFs using the **Adobe PDF Services API**. The pipeline converts unstructured PDF documents into clean, keyword-searchable JSON datasets suitable for downstream NLP or LLM workflows.

## Pipeline overview

```
Stage 1 — Extract   (01_extract.py)
  PDFs  →  one .zip file per PDF (contains structuredData.json)

Stage 2 — Merge     (02_merge.py)
  .zip files  →  merged_output.json  +  text_only_output.json

Stage 3 — Filter    (03_filter.py)
  merged_output.json  →  filtered structured JSON  +  filtered text-only JSON
```

### Output schema

**Structured JSON** (Stages 2 & 3):
```json
[
  {
    "File Name": "my_document",
    "Elements": [
      {"type": "heading",   "page": 1, "text": "Introduction"},
      {"type": "paragraph", "page": 1, "text": "...", "match_type": "direct"}
    ]
  }
]
```

**Text-only JSON** (Stages 2 & 3):
```json
[
  {
    "File Name": "my_document",
    "Text": "Introduction ... body text ...",
    "Term Count": 342
  }
]
```

Element types recognised: `title`, `heading`, `paragraph`, `paragraph_span`, `list_item`, `list_item_body`, `list_item_label`, `list`, `table`, `table_row`, `table_header_cell`, `table_cell`, `table_of_contents`, `table_of_contents_item`, `figure`, `footnote`, `aside`, `section`, `reference`, `style_span`, `subparagraph`, `watermark`, `other`.

---

## Prerequisites

- Python 3.10+
- An [Adobe PDF Services](https://developer.adobe.com/document-services/apis/pdf-extract/) account (free tier available)

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/your-username/adobe-pdf-extraction-pipeline.git
cd adobe-pdf-extraction-pipeline

# 2. Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
.venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure credentials
cp .env.example .env
# Edit .env and fill in your ADOBE_CLIENT_ID and ADOBE_CLIENT_SECRET
```

---

## Usage

### Stage 1 — Extract

```bash
python 01_extract.py \
  --pdf-folder  /path/to/pdfs \
  --zip-output  /path/to/zips
```

PDFs that already have a corresponding `.zip` file in `--zip-output` are skipped automatically.

### Stage 2 — Merge

```bash
python 02_merge.py \
  --zip-folder    /path/to/zips \
  --output-folder /path/to/output
```

### Stage 3 — Filter

```bash
# Keywords from the command line
python 03_filter.py \
  --input         /path/to/output/merged_output.json \
  --output-folder /path/to/filtered \
  --keywords "word one" "word two" \
  --allowed-types paragraph heading title \
  --min-words 10 \
  --require-alphabetic \
  --max-numeric-ratio 0.25 \
  --context

# Keywords from a JSON file
python 03_filter.py \
  --input          /path/to/output/merged_output.json \
  --output-folder  /path/to/filtered \
  --keywords-file  examples/keywords_example.json \
  --min-words 10 \
  --context
```

**Discover which element types are present in your dataset:**

```bash
python 03_filter.py --input merged_output.json --output-folder . --list-types
```

#### All Stage 3 options

| Flag | Description | Default |
|------|-------------|---------|
| `--keywords` | Space-separated keywords to match | (none, keep all) |
| `--keywords-file` | JSON file with keyword list | — |
| `--allowed-types` | Element types to keep | (all types) |
| `--min-words` | Min alphabetic tokens per element | 1 |
| `--require-alphabetic` | Drop elements with no letters | off |
| `--max-numeric-ratio` | Max numeric-token fraction (0–1) | 1.0 |
| `--context` | Include adaptive context around matches | on |
| `--no-context` | Disable context window | — |
| `--context-base-window` | Initial context window size (elements) | 1 |
| `--context-max-window` | Maximum context window size (elements) | 5 |
| `--context-min-words` | Min words for a context element to count | 20 |
| `--context-min-chars` | Min chars for a context element to count | 75 |
| `--text-separator` | Separator between elements in text-only output | `" "` |
| `--group-by-heading` | Group output by section headings | off |
| `--case-sensitive` | Case-sensitive keyword matching | off |
| `--start-keyword` | Start extracting at this heading | — |
| `--end-keyword` | Stop extracting at this heading | — |
| `--no-text-only` | Skip text-only output | — |
| `--no-structured` | Skip structured output | — |
| `--output-filename` | Custom structured output filename | auto-generated |
| `--text-only-filename` | Custom text-only output filename | auto-generated |
| `--list-types` | Print element types and exit | — |

---

## Credential management

Credentials are read from environment variables. Copy `.env.example` to `.env` and fill in your values:

```
ADOBE_CLIENT_ID=your_client_id_here
ADOBE_CLIENT_SECRET=your_client_secret_here
```

The `.env` file is listed in `.gitignore` and will never be committed. You can also pass credentials directly with `--client-id` / `--client-secret` (Stage 1 only).

---

## Project structure

```
.
├── 01_extract.py        Stage 1: PDF → zip via Adobe API
├── 02_merge.py          Stage 2: zip files → merged JSON datasets
├── 03_filter.py         Stage 3: keyword & type filtering
├── utils.py             Shared helpers (element-type mapping, text cleaning)
├── requirements.txt
├── .env.example
├── .gitignore
└── examples/
    └── keywords_example.json
```

---

## License

MIT © 2026 Andrea Andolfatto

## Author

Andrea Andolfatto
