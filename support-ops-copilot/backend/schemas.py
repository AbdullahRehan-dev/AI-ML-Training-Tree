"""
Every AIService function returns one of these models instead of raw text.
Pydantic does the validation; anything that doesn't fit the shape raises a
ValidationError, which reliability.py turns into a retry.
"""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field


class Classification(BaseModel):
    category: Literal[
        "billing", "technical", "shipping", "account", "refund_request",
        "product_question", "complaint", "other",
    ]
    urgency: Literal["low", "medium", "high", "critical"]
    reasoning: str = Field(description="One sentence on why this category/urgency")
    confidence: float = Field(ge=0.0, le=1.0)


class ExtractedData(BaseModel):
    customer_name: Optional[str] = None
    issue_summary: str
    order_id: Optional[str] = None
    email: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)


class DraftReply(BaseModel):
    reply: str
    tone: Literal["empathetic", "neutral", "apologetic", "informative"]
    confidence: float = Field(ge=0.0, le=1.0)


class Citation(BaseModel):
    source: str
    chunk_id: str
    snippet: str


class RAGAnswer(BaseModel):
    answer: str
    citations: list[Citation]
    confidence: float = Field(ge=0.0, le=1.0)


class ReviewFlag(BaseModel):
    flagged: bool
    threshold: float
    confidence: float
    reason: str


class ToolCallLogEntry(BaseModel):
    timestamp: str
    session_id: str
    tool_name: str
    tool_input: dict
    tool_output: Optional[dict] = None
    status: Literal["auto_executed", "pending_approval", "approved", "rejected", "error"]
    error: Optional[str] = None


class PipelineResult(BaseModel):
    ticket_text: str
    classification: Classification
    extracted: ExtractedData
    used_rag: bool
    rag_answer: Optional[RAGAnswer] = None
    draft: Optional[DraftReply] = None
    needs_agent_action: bool
    review: ReviewFlag
    session_id: Optional[str] = None
