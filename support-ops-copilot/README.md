# Support Ops Copilot

An AI-powered support assistant built in five stages on top of Grok
(xAI). Classifies tickets, answers from a real knowledge base with
citations, calls tools with a human-in-the-loop approval gate, and ships
with a working frontend that shows all of it happening live.

```
Stage 1  Core AI service (classify / draft / extract)
Stage 2  Validated JSON + retry + confidence scoring
Stage 3  RAG over a local knowledge base (ChromaDB)
Stage 4  Tool-calling agent with a human approval gate
Stage 5  One coherent app: pipeline + frontend + logs
```

## Project layout

```
support-ops-copilot/
├── backend/
│   ├── main.py                 FastAPI app - all HTTP endpoints
│   ├── config.py               env-driven settings
│   ├── grok_client.py          OpenAI-compatible client pointed at Groq Cloud
│   ├── schemas.py               Pydantic models (Stage 2 validated JSON)
│   ├── stage1_demo.py           Stage 1: raw, unhardened, run in terminal
│   ├── ai_service.py            Stage 1 functions, hardened per Stage 2
│   ├── reliability.py           retry-on-invalid-JSON + confidence gate
│   ├── pipeline.py              Stage 5: end-to-end ticket router
│   ├── knowledge_base/
│   │   ├── docs/                synthetic FAQ / policy / past tickets
│   │   ├── ingest.py            Stage 3: chunk + embed + store (ChromaDB)
│   │   └── retriever.py         Stage 3: retrieve + grounded, cited answer
│   ├── agent/
│   │   ├── tools.py              Stage 4: mock tools + fake order DB
│   │   └── agent.py              Stage 4: tool-calling loop + approval gate
│   └── logs/tool_call_log.jsonl  every tool call, input + output (generated)
├── frontend/
│   ├── index.html / style.css / app.js   plain HTML/CSS/JS, no build step
├── scripts/setup.sh              venv + install + build the RAG index
├── sample_tickets.json           tickets to try in the UI
├── BREAKING_IT.md                Stage 1 deliverable: documented failures
├── ARCHITECTURE.md               one-page architecture diagram (Mermaid)
└── requirements.txt
```

## Setup

Requires **Python 3.12** and a Groq Cloud API key from https://console.groq.com.

```bash
git clone <your-repo-url> support-ops-copilot
cd support-ops-copilot
bash scripts/setup.sh          # creates venv/, installs deps, builds the RAG index
```

`.env.example` copies `.env.example` to `.env` for you - open it and set:

```
GROQ_API_KEY=gsk-...your key...
GROK_MODEL=openai/gpt-oss-20b
GROQ_BASE_URL=https://api.groq.com/openai/v1
```

If you'd rather do it by hand:

```bash
python3.12 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then edit in your GROQ_API_KEY
python -m backend.knowledge_base.ingest   # builds the local vector index
```

## Running it

**Backend** (from the project root, venv activated):

```bash
uvicorn backend.main:app --reload --port 8000
```

**Frontend** - it's static, no build step. Either:

- Open `frontend/index.html` directly in a browser, or
- Serve it so relative paths behave the same as a real deployment:
  ```bash
  cd frontend && python -m http.server 5500
  # then open http://localhost:5500
  ```

The frontend has a "Backend URL" field in the top bar (defaults to
`http://localhost:8000`) - point it at wherever `uvicorn` is running.

## Trying each stage

- **Stage 1 (terminal, raw):** `python -m backend.stage1_demo` - runs the
  unhardened classify/draft/extract functions against sample tickets
  designed to break them (ambiguous input, prompt injection, hallucination
  bait). See `BREAKING_IT.md` for the write-up.
- **Stage 2/3/4/5 (frontend):** run the backend + open the frontend, then
  use the four tabs:
  - **Pipeline** - paste/pick a ticket, hit "Process ticket", watch the left
    rail light up through Classify → Knowledge → Act → Review.
  - **Agent & Tools** - give it a refund-shaped ticket (try the "Refund
    request within policy" sample), watch it call `lookup_order_status`,
    then pause with an approval modal before `issue_refund` executes.
  - **Knowledge Base** - ask something only the FAQ/policy docs would know
    (e.g. "do I pay a return shipping fee?") and see the cited chunks.
  - **Tool Call Log** - every tool call ever made, with input/output/status.

## API reference

| Endpoint | Stage | Purpose |
|---|---|---|
| `GET /api/health` | - | liveness check |
| `POST /api/classify` | 1/2 | `{ticket_text}` → `Classification` |
| `POST /api/extract` | 1/2 | `{ticket_text}` → `ExtractedData` |
| `POST /api/draft` | 1/2 | `{ticket_text, category?}` → `DraftReply` |
| `POST /api/rag/query` | 3 | `{question, top_k?}` → `RAGAnswer` w/ citations |
| `POST /api/agent/run` | 4 | `{ticket_text}` → session state, may be `pending_approval` |
| `POST /api/agent/approve` | 4 | `{session_id, approved}` → resumes the agent |
| `GET /api/agent/session/{id}` | 4 | current state of a session |
| `GET /api/agent/logs` | 4 | full tool-call log |
| `POST /api/pipeline/process` | 5 | `{ticket_text}` → full end-to-end `PipelineResult` |

## Design notes worth knowing before you demo this

- **Model:** defaults to `openai/gpt-oss-20b` for Groq Cloud OpenAI compatibility. Change
  `GROK_MODEL` in `.env` if you want a cheaper/faster variant - check your
  Groq Cloud console for what's current, since model slugs and access vary by key.
- **Embeddings are local, not Groq:** Groq doesn't expose an embeddings
  endpoint, so Stage 3 uses `sentence-transformers` (`all-MiniLM-L6-v2`)
  running on your machine, with ChromaDB for storage. Groq is only used for
  the final grounded-answer generation, not the retrieval step.
- **Agent sessions are in-memory:** fine for a demo/single-process app;
  restart the backend and pending sessions/log history from that process
  reset (the JSONL log file itself persists on disk across restarts).
- **Refund tool caps:** `issue_refund` mirrors `backend/knowledge_base/docs/policy.md`
  - it hard-rejects anything over $500 (should be escalated to finance
    instead) and flags $150-$500 as needing manager approval, on top of the
    human approval gate that already applies to every refund regardless of
  amount.

## Git history

For the "commit history shows progressive build-up" checklist item, the
natural way to build this is stage-by-stage commits, e.g.:

```bash
git init
git add backend/schemas.py backend/grok_client.py backend/config.py \
        backend/stage1_demo.py BREAKING_IT.md requirements.txt .env.example .gitignore
git commit -m "Stage 1: core AI service + documented failures"

git add backend/reliability.py backend/ai_service.py
git commit -m "Stage 2: validated JSON, retry logic, confidence scoring"

git add backend/knowledge_base/
git commit -m "Stage 3: RAG over local knowledge base with citations"

git add backend/agent/
git commit -m "Stage 4: tool-calling agent with human approval gate"

git add backend/pipeline.py backend/main.py frontend/ scripts/ sample_tickets.json ARCHITECTURE.md README.md
git commit -m "Stage 5: end-to-end pipeline + frontend + architecture diagram"
```

## What's next / what I'd change

- Swap in-memory agent sessions for Redis (or a DB) so it survives a
  restart and works across multiple backend workers.
- Add streaming responses to the frontend so drafts/answers appear
  token-by-token instead of all at once.
- Real order/payment system integration in `backend/agent/tools.py` instead
  of the mock in-memory DB.
- Auth on the FastAPI app before this ever sees a real customer's data - it
  is wide open (`allow_origins=["*"]`) by design for local demo purposes.
