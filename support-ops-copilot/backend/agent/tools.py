"""
Stage 4 - Give It Hands.

Three mock tools, backed by an in-memory fake order DB (synthetic - swap
for real order-system/payment-gateway calls in production). Each tool
function does real validation and can genuinely raise, so
agent.py's error handling has something real to catch.
"""
from __future__ import annotations

# Fake order database - keyed by order_id
MOCK_ORDERS: dict[str, dict] = {
    "A1092": {"status": "processing", "item": "Blender", "amount": 89.99, "delivered": False},
    "A7734": {"status": "delivered", "item": "Jacket (blue)", "amount": 64.00, "delivered": True},
    "B1120": {"status": "delivered", "item": "Desk Lamp", "amount": 42.50, "delivered": True},
    "B4471": {"status": "delivered", "item": "Wireless Headphones", "amount": 129.99, "delivered": True},
    "C2001": {"status": "shipped", "item": "Yoga Mat", "amount": 34.50, "delivered": False},
}

# Refunds already issued this session, so an approved refund can't be replayed
_ISSUED_REFUNDS: dict[str, dict] = {}

# Refund cap that a support agent (human or AI) can authorize without manager
# sign-off - mirrors backend/knowledge_base/docs/policy.md
SUPPORT_REFUND_LIMIT = 150.00


class ToolError(Exception):
    """Raised by a tool on bad input / business-rule violation. Caught by the
    agent loop and turned into a tool error message fed back to the model -
    never a silent failure or a crash."""


def lookup_order_status(order_id: str) -> dict:
    order_id = (order_id or "").strip().upper()
    order = MOCK_ORDERS.get(order_id)
    if not order:
        raise ToolError(f"No order found with ID '{order_id}'.")
    return {"order_id": order_id, **order}


def issue_refund(order_id: str, amount: float, reason: str) -> dict:
    order_id = (order_id or "").strip().upper()
    order = MOCK_ORDERS.get(order_id)
    if not order:
        raise ToolError(f"Cannot refund - no order found with ID '{order_id}'.")
    if amount <= 0:
        raise ToolError("Refund amount must be greater than zero.")
    if amount > order["amount"]:
        raise ToolError(
            f"Refund amount ${amount:.2f} exceeds the original order amount ${order['amount']:.2f}."
        )
    if order_id in _ISSUED_REFUNDS:
        raise ToolError(f"Order '{order_id}' has already been refunded this session.")
    if amount > 500:
        raise ToolError(
            f"Refund of ${amount:.2f} exceeds the $500 support-tool limit and must be "
            f"escalated to the finance team per policy - use escalate_to_human instead."
        )

    record = {
        "order_id": order_id,
        "amount": round(amount, 2),
        "reason": reason,
        "requires_manager_approval": amount > SUPPORT_REFUND_LIMIT,
        "status": "issued",
    }
    _ISSUED_REFUNDS[order_id] = record
    return record


def escalate_to_human(reason: str, order_id: str | None = None) -> dict:
    if not reason or not reason.strip():
        raise ToolError("An escalation reason is required.")
    return {
        "escalated": True,
        "order_id": order_id,
        "reason": reason,
        "queue": "human_support_l2",
    }


# Tools that move money / take irreversible action - these are the ones that
# MUST pause for human approval before executing (Stage 4 requirement).
DESTRUCTIVE_TOOLS = {"issue_refund"}

TOOL_IMPLEMENTATIONS = {
    "lookup_order_status": lookup_order_status,
    "issue_refund": issue_refund,
    "escalate_to_human": escalate_to_human,
}

# OpenAI/Grok function-calling tool schemas
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_order_status",
            "description": "Look up the current status, item, and amount of an order by its order ID. Read-only.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "Order ID, e.g. 'A1092'"},
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "issue_refund",
            "description": (
                "Issue a refund for an order. DESTRUCTIVE - moves real money. "
                "Requires human approval before it actually executes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "amount": {"type": "number", "description": "Refund amount in USD"},
                    "reason": {"type": "string"},
                },
                "required": ["order_id", "amount", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_human",
            "description": "Escalate this ticket to a human support agent's queue with a reason.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string"},
                    "order_id": {"type": "string"},
                },
                "required": ["reason"],
            },
        },
    },
]
