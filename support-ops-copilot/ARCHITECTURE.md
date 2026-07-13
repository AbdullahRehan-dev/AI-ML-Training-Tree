# Architecture

One page, top to bottom: a ticket comes in, gets classified, optionally
grounded against the knowledge base, optionally handed to the tool-calling
agent, and anything uncertain or destructive stops for a human.

```mermaid
flowchart TD
    U[Reviewer submits raw ticket<br/>via frontend] --> API[FastAPI backend<br/>backend/main.py]

    API --> CLS["Stage 1/2: classify_ticket + extract_ticket_data<br/>(ai_service.py -> reliability.py)<br/>validated JSON, retry x3, confidence score"]

    CLS -->|category needs<br/>knowledge base| RAG["Stage 3: RAG<br/>retriever.py<br/>ChromaDB top-k -> Grok grounded answer + citations"]
    CLS -->|otherwise| DRAFT["draft_reply()<br/>plain drafted reply"]
    RAG -->|no good match found| DRAFT

    CLS -->|category/keywords suggest<br/>refund or account action| AGENT["Stage 4: Agent + Tools<br/>agent.py<br/>lookup_order_status / issue_refund / escalate_to_human"]
    AGENT -->|destructive tool call| GATE{{Human approval gate}}
    GATE -->|approve| EXEC[Tool executes for real]
    GATE -->|reject| SKIP[Model informed, adapts]
    EXEC --> LOG[(tool_call_log.jsonl<br/>every input + output)]
    SKIP --> LOG

    CLS --> CONF{{Confidence < threshold<br/>OR urgency = critical?}}
    RAG --> CONF
    DRAFT --> CONF
    CONF -->|yes| REVIEW[Flagged for human review]
    CONF -->|no| AUTO[Auto-approved response]

    RAG -.->|cited chunks| KB[(ChromaDB<br/>FAQ / policy / past tickets)]

    REVIEW --> UI[Frontend: classification,<br/>draft/RAG answer + citations,<br/>review flag, approval modal, tool-call log]
    AUTO --> UI
    LOG --> UI
```

## Component notes

- **Stage 1/2 (`ai_service.py` + `reliability.py`)** - every AI call goes
  through `call_structured()`, which asks Grok for JSON, validates it against
  a Pydantic schema, retries up to 3x on failure, and raises a caught
  `StructuredGenerationError` (never a raw crash) if it still can't get valid
  output. Every schema carries a `confidence` field.
- **Stage 3 (`knowledge_base/`)** - docs are chunked by markdown section,
  embedded locally with `sentence-transformers` (no API cost for embeddings),
  and stored in a persistent local ChromaDB collection. Answers are
  generated only from retrieved chunks, and citations are cross-checked
  against what was actually retrieved before being returned to the UI.
- **Stage 4 (`agent/`)** - a real OpenAI-style tool-calling loop against
  Grok. `issue_refund` is the one destructive tool; the loop pauses and
  returns `status: pending_approval` instead of executing it, and only
  proceeds after `/api/agent/approve` is called. Every tool call (auto or
  approved/rejected/errored) is appended to `backend/logs/tool_call_log.jsonl`.
- **Stage 5 (`pipeline.py`)** - the single function the frontend's main
  "Process Ticket" flow calls: classify -> retrieve if it's a knowledge
  question -> draft or flag for agent action -> compute an overall confidence
  and apply the review gate (also force-flagging anything urgency=critical,
  per `backend/knowledge_base/docs/policy.md`).
- **Frontend (`frontend/`)** - a static HTML/CSS/JS single page. The
  left-hand pipeline rail lights up each stage live as a ticket moves
  through it; results render as cards (classification, extracted data,
  grounded answer + citation chips, or agent tool-call thread with an
  inline approve/reject control); a live log panel mirrors
  `tool_call_log.jsonl`.
