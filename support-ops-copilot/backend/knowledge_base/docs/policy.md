# Support Policy

## Refund authorization limits
Support agents (human or AI) may authorize refunds up to $150 without
manager approval. Refunds between $150 and $500 require a manager's sign-off
before processing. Refunds above $500 must be escalated to the finance team
and cannot be processed through the standard support refund tool. Any
refund, regardless of amount, must be logged with the order ID, amount, and
reason before being issued.

## Escalation criteria
A ticket should be escalated to a human agent if any of the following are
true: the customer explicitly asks for a human, the issue involves a refund
over $150, the customer mentions legal action or a chargeback/dispute
already filed with their bank, the ticket involves a safety issue (e.g. a
product injury claim), or the AI assistant's confidence in its own
classification or drafted response is below the configured threshold.

## Tone and communication standards
All customer replies must be empathetic and non-defensive, even when the
customer is upset or the company is not at fault. Agents should never blame
the customer, never argue about policy in the first reply (acknowledge
first, explain policy second), and should always give the customer a clear
next step or timeframe.

## Data the assistant may reference
The assistant may only state order details, dates, or amounts that come from
a verified tool call (e.g. `lookup_order_status`) or from this knowledge
base. It must never state a specific date, amount, or order status that it
has not retrieved from a trusted source.

## Prohibited actions without human approval
No refund, account credit, or account cancellation may be executed
automatically without an explicit human approval step, regardless of the
AI's confidence level. Read-only actions (looking up an order, checking a
policy) do not require approval.

## Priority/SLA guidance
Critical-urgency tickets (e.g. security concerns, payment fraud, safety
issues) must be flagged for human review within the same response, even if
the AI's confidence is otherwise high - urgency alone is grounds for review
on top of the confidence threshold.
