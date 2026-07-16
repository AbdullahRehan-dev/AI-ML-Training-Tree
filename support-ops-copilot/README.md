# Support Ops Copilot

A demo support-assistant app built around Groq Cloud and local retrieval.
It classifies support tickets, extracts structured issue data, answers policy/
FAQ questions with citations, and runs agent-enabled refund/order actions
behind a human approval gate.

## What this project actually does

- Stage 1: classify ticket intent and urgency, extract order/customer fields,
  and draft a support reply.
- Stage 2: validate all model responses as structured JSON, retry if the
  output is invalid, and gate risky outputs with confidence scoring.
- Stage 3: retrieve grounded answers from a local ChromaDB knowledge base.
- Stage 4: run a tool-calling agent for refund/order requests with an
  approval pause before destructive actions.
- Stage 5: expose a single pipeline endpoint plus a static frontend that
  shows the entire ticket flow.

## Repository layout

```
support-ops-copilot/
├── backend/
│   ├── main.py                 FastAPI app and HTTP endpoints
│   ├── config.py               environment-driven project settings
│   ├── grok_client.py          OpenAI-compatible Groq client wrapper
│   ├── schemas.py              Pydantic models for all structured outputs
│   ├── stage1_demo.py          terminal-only Stage 1 demo runner
│   ├── ai_service.py           classification, extraction, reply drafting
│   ├── reliability.py          JSON validation, retry logic, confidence gate
│   ├── pipeline.py             end-to-end ticket router
│   ├── knowledge_base/
│   │   ├── docs/               FAQ, policy, and past-ticket source docs
│   │   ├── ingest.py           chunk + embed + store the local vector index
   │   └── retriever.py         retrieval + grounded answer generation
│   ├── agent/
│   │   ├── tools.py            mock order/refund tools and policy guardrails
│   │   └── agent.py            tool-calling loop with approval gating
│   └── logs/tool_call_log.jsonl recorded tool call events
├── frontend/
│   ├── index.html              static web UI
│   ├── style.css               UI styling
│   └── app.js                  frontend behavior and API integration
├── scripts/setup.sh            creates venv, installs deps, builds RAG index
├── requirements.txt            Python dependencies
├── sample_tickets.json         example tickets for manual testing
├── BREAKING_IT.md              prompt injection / failure case notes
└── ARCHITECTURE.md             architecture and component diagram
```

## Requirements

- Python 3.12 (or a compatible Python 3.x install)
- A Groq Cloud API key
- `python-dotenv` support is required to load `.env`

## Setup

From the project root:

```bash
bash scripts/setup.sh
```

This does the following:

1. creates and activates `venv/`
2. installs dependencies from `requirements.txt`
3. copies `.env.example` to `.env` if needed
4. builds the local ChromaDB knowledge base index

Then edit `.env` and add your `GROQ_API_KEY`.

If you prefer manual setup:

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and add GROQ_API_KEY
python -m backend.knowledge_base.ingest
```

### Required `.env` values

```
GROQ_API_KEY=gsk-...your key...
GROK_MODEL=openai/gpt-oss-20b
GROQ_BASE_URL=https://api.groq.com/openai/v1
```

Optional overrides:

```
CONFIDENCE_THRESHOLD=0.7
MAX_RETRIES=3
CHROMA_PERSIST_DIR=./data/chroma_db
```

## Running the app

Start the backend from the repository root:

```bash
uvicorn backend.main:app --reload --port 8000
```

**Frontend** - it's static, no build step. You can open `frontend/index.html` directly in a browser, or serve it from the backend at `http://localhost:8000`.

If you prefer a separate static host, use:

```bash
cd frontend && python -m http.server 8000
```

Then open `http://localhost:8000` and make sure the Backend URL in the UI matches `http://localhost:8000`.

## What to try in the UI

- **Pipeline**: process a ticket end-to-end. The UI shows classification,
  knowledge retrieval/drafting, agent action detection, and review state.
- **Agent & Tools**: run a refund/order ticket through the agent and
  approve or reject destructive tool calls.
- **Knowledge Base**: ask a policy/FAQ question and see citations from the
  local knowledge docs.
- **Tool Call Log**: inspect every recorded tool call, including input,
  output, and approval status.

## Key behavior

- `backend.pipeline.process` performs classify → extract → optional RAG →
  draft → review gating.
- Low-confidence outputs are flagged for review by `backend.reliability`.
- Tickets matching refund/order criteria launch the agent via
  `backend.agent.agent.run_agent`.
- The agent pauses for human approval before any destructive tool
  invocation such as `issue_refund`.
- Tool call events are appended to `backend/logs/tool_call_log.jsonl`.

## API reference

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Backend liveness check |
| `POST /api/classify` | Classify ticket text |
| `POST /api/extract` | Extract structured ticket fields |
| `POST /api/draft` | Draft a response from ticket text |
| `POST /api/rag/query` | Query the local RAG knowledge base |
| `POST /api/agent/run` | Start an agent session for a ticket |
| `POST /api/agent/approve` | Approve or reject pending agent actions |
| `GET /api/agent/session/{id}` | Get current agent session state |
| `GET /api/agent/logs` | Fetch recorded tool-call logs |
| `POST /api/pipeline/process` | Run the full ticket pipeline end-to-end |

## Notes

- The Groq client is used only for classification, extraction, drafting, and
  grounded response generation. Embeddings are built locally with
  `sentence-transformers` and stored in ChromaDB.
- Agent sessions are held in memory, so restarting the backend clears
  pending sessions and session-specific state.
- The refund/order tools are mock implementations in
  `backend/agent/tools.py` and are meant for demo/testing only.
- The frontend is intentionally simple: no build step, just plain HTML/CSS/JS.

## Known limitations

- No authentication or authorization is implemented.
- In-memory agent sessions do not survive backend restarts.
- The demo order/refund tools are not integrated with a real backend.
- The app assumes a local Groq Cloud API key and may need model slug
  updates based on your account.

## Recommended git history approach

For a clean stage-by-stage commit history, use:

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

## Future improvements

- Replace in-memory agent sessions with Redis or a durable DB.
- Add authentication for backend API and frontend access.
- Integrate real order/payment systems in `backend/agent/tools.py`.
- Add streaming output to the frontend for better UX.
