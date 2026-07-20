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


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Run the full Support Ops Copilot pipeline on a ticket text."
    )
    parser.add_argument(
        "ticket_text",
        nargs="+",
        help="The ticket text to process through the full pipeline.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full pipeline result as JSON.",
    )
    args = parser.parse_args()

    ticket_text = " ".join(args.ticket_text)
    result = process_ticket(ticket_text)

    if args.json:
        print(json.dumps(result.model_dump(), indent=2, default=str))
        raise SystemExit(0)

    print(f"ticket_text: {result.ticket_text}\n")
    print(f"category: {result.classification.category}")
    print(f"urgency: {result.classification.urgency}")
    print(f"confidence: {result.classification.confidence}\n")
    print(f"issue_summary: {result.extracted.issue_summary}")

    if result.used_rag and result.rag_answer is not None:
        print("RAG answer:")
        print(result.rag_answer.answer)
        if result.rag_answer.citations:
            print("citations:")
            for citation in result.rag_answer.citations:
                print(f"- {citation}")
        print("")
    elif result.draft is not None:
        print(f"draft: {result.draft.text}\n")
    else:
        print("draft: <no draft generated>\n")

    print(f"needs agent action: {result.needs_agent_action}")
    if result.session_id:
        print(f"agent session id: {result.session_id}")
        print(f"agent status: {result.agent_status}")
        if result.pending_approval is not None:
            print(f"pending approval: {result.pending_approval}")
    print(f"review flagged: {result.review.flagged}")
    print(f"review reason: {result.review.reason}")
