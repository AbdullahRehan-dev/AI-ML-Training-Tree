# Mini RAG System

Ask a question, get an answer sourced from a real PDF you provide — not a
hardcoded sample.

## How it works (the 5 steps)

```
 your.pdf
    │
    ▼
[1] pdf_loader.py   -> extract text, page by page
    │
    ▼
[2] chunker.py       -> split into overlapping ~800-char chunks
    │
    ▼
[3] embedder.py      -> turn each chunk into a vector (local, offline)
    │
    ▼
[4] vector_store.py  -> store vectors in ChromaDB (on disk, ./chroma_db)
    │
    ▼
   ... later, when you ask a question ...
    │
[4] embed the question -> retrieve top 3 most similar chunks
    │
    ▼
[5] rag_pipeline.py  -> send those 3 chunks + your question to Grok
    │
    ▼
   a grounded answer, with page citations
```

`rag_pipeline.py` is the conductor — it's the only file that talks to all
the other modules. Everything else (`pdf_loader`, `chunker`, `embedder`,
`vector_store`) does one job and doesn't know the others exist, so you can
test or swap any one piece without touching the rest.

## Design choices worth knowing about

- **Embeddings run locally, for free.** `embedder.py` uses ChromaDB's
  built-in embedding model (`all-MiniLM-L6-v2`, via onnxruntime) instead of
  an API call or a full PyTorch install. It downloads once (a few dozen MB)
  and is cached — after that, embedding is fully offline and instant.
- **Generation uses Grok.** xAI's API is OpenAI-compatible, so the project
  just uses the standard `openai` Python SDK pointed at `https://api.x.ai/v1`.
  That's the only place an external API call happens.
- **Chunks carry page numbers.** Chunking never crosses a page boundary, so
  every retrieved chunk — and the final answer — can cite *which page* it
  came from, not just "somewhere in the document".
- **Fresh PDF = fresh index.** Loading a new PDF wipes the old ChromaDB
  collection first, so answers from a previous document never leak into a
  new one.
- **The model refuses to guess.** The system prompt tells Grok to answer
  only from the retrieved chunks, and to say so explicitly if the answer
  isn't in them — that's what makes it "grounded" rather than "inspired by".

## Setup

Works with Python 3.14 (also fine on 3.10+). Confirmed dependency versions:
- `chromadb`, `pypdf`, and `openai` all publish Python 3.14 wheels.
- No PyTorch dependency, so there's nothing here that lags behind a brand
  new Python release.

```bash
# 1. Create and activate a virtual environment
python3.14 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your Grok API key
cp .env.example .env
# then edit .env and paste your key:
#   XAI_API_KEY=xai-...
```

Get a key at [console.x.ai](https://console.x.ai) if you don't have one yet.

## Running it

```bash
python main.py path/to/your.pdf
```

or run it with no argument and it'll prompt you for a path:

```bash
python main.py
```

First run will download the embedding model (one-time, needs internet).
After ingestion finishes you'll see a prompt:

```
=== Mini RAG System ===

Ingesting 'your.pdf' ...
Done. Indexed 47 chunks into ChromaDB.

Ask a question about the document (type 'exit' to quit,
or 'load <path>' to switch to a different PDF).

> what does this document say about pricing?

Based on page 3, the document states that pricing is tiered by usage volume...

Sources:
  [1] page 3: "Our pricing model scales with monthly active users..."
  [2] page 3: "Enterprise customers receive custom quotes based on..."
  [3] page 7: "Discounts apply for annual commitments over..."

> load other-document.pdf
Loaded 'other-document.pdf' -- 32 chunks indexed.

> exit
```

Type `load <path>` at any time to swap in a different PDF without
restarting the program. Type `exit` or `quit` to leave.

## Tuning

All the knobs live in `config.py`:

| Constant | What it controls |
|---|---|
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | How big chunks are and how much they overlap |
| `TOP_K` | How many chunks get retrieved per question (default 3) |
| `XAI_MODEL` | Which Grok model generates the answer (default `grok-4.3`) |

## Troubleshooting

- **"XAI_API_KEY is not set"** — make sure `.env` exists (copied from
  `.env.example`) and has your real key, in the same folder you run
  `python main.py` from.
- **"No extractable text found in ... "** — the PDF is likely
  scanned/image-only. This project doesn't do OCR, so text extraction
  needs a PDF with a real text layer.
- **First run is slow** — that's the one-time embedding model download.
  Subsequent runs are fast since it's cached locally.
