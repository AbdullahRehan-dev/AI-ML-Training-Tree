"""
Stage 5 - Ship It.

One function that ties every earlier stage together the way the frontend's
"Process Ticket" button actually uses the app:

    classify -> extract -> (retrieve knowledge if it's a knowledge question)
             -> draft a reply (grounded in retrieved knowledge if we used it)
             -> flag for human review if confidence is low OR urgency is critical
             -> flag for agent/tool action if it looks like a refund/order request
"""
from __future__ import annotations

from backend.ai_service import classify_ticket, extract_ticket_data, draft_reply, StructuredGenerationError
from backend.agent import agent as agent_module
from backend.knowledge_base.retriever import answer_from_knowledge_base
from backend.reliability import build_review_flag
from backend.schemas import PipelineResult, Classification, ExtractedData, DraftReply, ReviewFlag

# Categories where the customer is most likely asking something answerable
# from the FAQ/policy knowledge base, rather than something needing an
# account-specific action.
KNOWLEDGE_CATEGORIES = {"shipping", "product_question", "account", "billing"}

# Categories/signals that mean this ticket likely needs a tool-calling agent
# (order lookups, refunds, escalation) rather than just a drafted reply.
ACTION_CATEGORIES = {"refund_request"}
ACTION_KEYWORDS = ("refund", "money back", "charge back", "chargeback", "cancel my order")


def _needs_agent_action(classification: Classification, ticket_text: str) -> bool:
    if classification.category in ACTION_CATEGORIES:
        return True
    lowered = ticket_text.lower()
    return any(kw in lowered for kw in ACTION_KEYWORDS)


def process_ticket(ticket_text: str) -> PipelineResult:
    classification = classify_ticket(ticket_text)
    extracted = extract_ticket_data(ticket_text)

    used_rag = classification.category in KNOWLEDGE_CATEGORIES
    rag_answer = None
    draft = None

    if used_rag:
        rag_answer = answer_from_knowledge_base(ticket_text)
        # If retrieval genuinely found nothing useful, fall back to a normal
        # drafted reply instead of shipping "I don't have information on that."
        if not rag_answer.citations:
            used_rag = False
            draft = draft_reply(ticket_text, category=classification.category)
    else:
        draft = draft_reply(ticket_text, category=classification.category)

    needs_agent_action = _needs_agent_action(classification, ticket_text)

    session_id = None
    agent_status = None
    pending_approval = None
    if needs_agent_action:
        try:
            session = agent_module.run_agent(ticket_text)
        except Exception as e:
            raise RuntimeError(f"Agent failed during pipeline: {e}") from e
        session_id = session["session_id"]
        agent_status = session["status"]
        pending_approval = session.get("pending_approval")

    confidences = [classification.confidence, extracted.confidence]
    confidences.append(rag_answer.confidence if rag_answer else draft.confidence)
    overall_confidence = min(confidences)

    review = build_review_flag(overall_confidence, context=f"category={classification.category}")
    if classification.urgency == "critical" and not review.flagged:
        review = ReviewFlag(
            flagged=True,
            threshold=review.threshold,
            confidence=review.confidence,
            reason=f"{review.reason}; also flagged because urgency=critical per policy.",
        )

    return PipelineResult(
        ticket_text=ticket_text,
        classification=classification,
        extracted=extracted,
        used_rag=used_rag,
        rag_answer=rag_answer,
        draft=draft,
        needs_agent_action=needs_agent_action,
        review=review,
        agent_status=agent_status,
        pending_approval=pending_approval,
        session_id=session_id,
    )
