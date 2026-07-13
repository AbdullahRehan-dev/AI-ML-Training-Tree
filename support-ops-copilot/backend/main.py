"""
Support Ops Copilot - FastAPI app.

Run with:
    uvicorn backend.main:app --reload --port 8000

Endpoints map directly to the five stages - see README.md for the full list.
"""
from __future__ import annotations
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend import ai_service
from backend.pipeline import process_ticket
from backend.knowledge_base.retriever import answer_from_knowledge_base
from backend.agent import agent as agent_module
from backend.reliability import StructuredGenerationError

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Support Ops Copilot", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo project - lock this down to your frontend origin in production
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def serve_frontend():
    return FileResponse(FRONTEND_DIR / "index.html")


# ---------- request bodies ----------

class TicketBody(BaseModel):
    ticket_text: str


class DraftBody(BaseModel):
    ticket_text: str
    category: str | None = None


class RAGQueryBody(BaseModel):
    question: str
    top_k: int = 3


class ApproveBody(BaseModel):
    session_id: str
    approved: bool


# ---------- error helper ----------

def _handle_generation_error(e: StructuredGenerationError):
    raise HTTPException(
        status_code=502,
        detail={
            "message": str(e),
            "last_raw_output": e.last_raw_output,
            "hint": "The model failed to produce valid structured output after all retries.",
        },
    )


# ---------- health ----------

@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---------- Stage 1/2: core AI service ----------

@app.post("/api/classify")
def classify(body: TicketBody):
    try:
        return ai_service.classify_ticket(body.ticket_text)
    except StructuredGenerationError as e:
        _handle_generation_error(e)


@app.post("/api/extract")
def extract(body: TicketBody):
    try:
        return ai_service.extract_ticket_data(body.ticket_text)
    except StructuredGenerationError as e:
        _handle_generation_error(e)


@app.post("/api/draft")
def draft(body: DraftBody):
    try:
        return ai_service.draft_reply(body.ticket_text, category=body.category)
    except StructuredGenerationError as e:
        _handle_generation_error(e)


# ---------- Stage 3: RAG ----------

@app.post("/api/rag/query")
def rag_query(body: RAGQueryBody):
    try:
        return answer_from_knowledge_base(body.question, top_k=body.top_k)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except StructuredGenerationError as e:
        _handle_generation_error(e)


# ---------- Stage 4: agent + tools ----------

@app.post("/api/agent/run")
def agent_run(body: TicketBody):
    try:
        return agent_module.run_agent(body.ticket_text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Agent run failed: {e}")


@app.post("/api/agent/approve")
def agent_approve(body: ApproveBody):
    try:
        return agent_module.approve_pending(body.session_id, body.approved)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get("/api/agent/session/{session_id}")
def agent_session(session_id: str):
    try:
        return agent_module.get_session(session_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/agent/logs")
def agent_logs(limit: int = 200):
    return agent_module.get_logs(limit=limit)


# ---------- Stage 5: end-to-end pipeline ----------

@app.post("/api/pipeline/process")
def pipeline_process(body: TicketBody):
    try:
        return process_ticket(body.ticket_text)
    except StructuredGenerationError as e:
        _handle_generation_error(e)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
