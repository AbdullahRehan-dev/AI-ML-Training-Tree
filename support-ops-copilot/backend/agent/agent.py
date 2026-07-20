"""
Stage 4 - Give It Hands - Agent + Tools.

A minimal but real tool-calling loop against Grok's function-calling API.
Sessions are kept in memory (fine for a single-process demo/capstone; swap
for redis/a DB for multi-worker deployments) so the frontend can:

  1. POST /api/agent/run          -> starts the loop, may come back "pending_approval"
  2. POST /api/agent/approve      -> resumes after a human approves/rejects
  3. GET  /api/agent/logs         -> see every tool call, input + output, ever made

Every tool call - auto-executed or approved/rejected - is appended to
backend/logs/tool_call_log.jsonl. Tool errors are caught and turned into a
tool result message the model can react to, never a silent failure.
"""
from __future__ import annotations
import json
import time
import uuid
import datetime
from typing import Any

from backend.grok_client import client, DEFAULT_MODEL
from backend.agent.tools import (
    TOOL_SCHEMAS, TOOL_IMPLEMENTATIONS, DESTRUCTIVE_TOOLS, ToolError,
)
from backend import config
from backend.schemas import ToolCallLogEntry

AGENT_SYSTEM = """You are a support agent with tools. Use lookup_order_status
to check real order data before saying anything about an order - never
guess order status, dates, or amounts. Use issue_refund only when the
customer has a legitimate refund request you've verified against the order
(don't refund more than the order amount). Use escalate_to_human for
anything outside policy, over the refund limit, or where the customer
explicitly asks for a human. When you're done, give a final plain-language
summary of what you did/found for the customer - no more tool calls."""

MAX_TOOL_ITERATIONS = 6

# session_id -> {"messages": [...], "status": ..., "pending": {...}|None, "final_answer": str|None}
_SESSIONS: dict[str, dict[str, Any]] = {}


def _log(session_id: str, tool_name: str, tool_input: dict, tool_output: dict | None,
          status: str, error: str | None = None) -> None:
    entry = ToolCallLogEntry(
        timestamp=datetime.datetime.utcnow().isoformat() + "Z",
        session_id=session_id,
        tool_name=tool_name,
        tool_input=tool_input,
        tool_output=tool_output,
        status=status,
        error=error,
    )
    with open(config.TOOL_CALL_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(entry.model_dump_json() + "\n")


def get_logs(limit: int = 200) -> list[dict]:
    if not config.TOOL_CALL_LOG_PATH.exists():
        return []
    lines = config.TOOL_CALL_LOG_PATH.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(line) for line in lines[-limit:]][::-1]


def _execute_tool(session_id: str, tool_name: str, tool_args: dict) -> dict:
    """Run a tool, catch errors gracefully, log input+output either way."""
    impl = TOOL_IMPLEMENTATIONS.get(tool_name)
    if impl is None:
        err = f"Unknown tool '{tool_name}'"
        _log(session_id, tool_name, tool_args, None, status="error", error=err)
        return {"error": err}
    try:
        output = impl(**tool_args)
        _log(session_id, tool_name, tool_args, output, status="approved" if tool_name in DESTRUCTIVE_TOOLS else "auto_executed")
        return output
    except ToolError as e:
        _log(session_id, tool_name, tool_args, None, status="error", error=str(e))
        return {"error": str(e)}
    except Exception as e:  # never let a tool crash the whole request
        _log(session_id, tool_name, tool_args, None, status="error", error=f"Unexpected error: {e}")
        return {"error": f"Unexpected error running {tool_name}: {e}"}


def _normalize_tool_name(tool_name: str) -> str:
    if tool_name in TOOL_IMPLEMENTATIONS:
        return tool_name
    for valid_name in TOOL_IMPLEMENTATIONS:
        if valid_name in tool_name:
            return valid_name
    return tool_name


def _call_model(session: dict) -> Any:
    return client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=session["messages"],
        tools=TOOL_SCHEMAS,
        tool_choice="auto",
        temperature=0.2,
        max_tokens=800,
    )


def _advance(session_id: str) -> dict:
    """
    Drive the loop forward until we either finish, need approval, or hit the
    iteration cap. Returns the current public-facing session state.
    """
    session = _SESSIONS[session_id]

    for _ in range(MAX_TOOL_ITERATIONS):
        response = _call_model(session)
        msg = response.choices[0].message
        tool_calls = msg.tool_calls or []

        if not tool_calls:
            session["status"] = "done"
            session["final_answer"] = msg.content or ""
            session["messages"].append({"role": "assistant", "content": msg.content or ""})
            break

        # Record the assistant's tool-call message so the conversation stays valid
        session["messages"].append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [tc.model_dump() for tc in tool_calls],
        })

        # Process tool calls one at a time; stop at the first destructive one
        # that needs approval, and hold any remaining calls for after resume.
        made_progress = False
        for i, tc in enumerate(tool_calls):
            raw_tool_name = tc.function.name
            tool_name = _normalize_tool_name(raw_tool_name)
            try:
                tool_args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                tool_args = {}

            if tool_name not in TOOL_IMPLEMENTATIONS:
                session["status"] = "done"
                session["final_answer"] = (
                    f"Agent attempted to call an unknown tool: {raw_tool_name}. "
                    "Please try again with a different ticket or update the tool schema."
                )
                session["messages"].append({"role": "assistant", "content": session["final_answer"]})
                _log(session_id, raw_tool_name, tool_args, None, status="error", error="Unknown tool call")
                return _public_state(session_id)

            if tool_name in DESTRUCTIVE_TOOLS:
                session["status"] = "pending_approval"
                session["pending"] = {
                    "tool_call_id": tc.id,
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                    "remaining_tool_calls": [t.model_dump() for t in tool_calls[i + 1:]],
                }
                _log(session_id, tool_name, tool_args, None, status="pending_approval")
                made_progress = False
                break

            output = _execute_tool(session_id, tool_name, tool_args)
            session["messages"].append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(output),
            })
            made_progress = True
        else:
            # no destructive break hit; loop again to let the model react
            continue

        if session["status"] == "pending_approval":
            break
        if not made_progress:
            break

    return _public_state(session_id)


def _public_state(session_id: str) -> dict:
    session = _SESSIONS[session_id]
    state = {
        "session_id": session_id,
        "status": session["status"],
        "final_answer": session.get("final_answer"),
    }
    if session["status"] == "pending_approval":
        pending = session["pending"]
        state["pending_approval"] = {
            "tool_name": pending["tool_name"],
            "tool_args": pending["tool_args"],
        }
    return state


def run_agent(ticket_text: str) -> dict:
    session_id = str(uuid.uuid4())
    _SESSIONS[session_id] = {
        "messages": [
            {"role": "system", "content": AGENT_SYSTEM},
            {"role": "user", "content": ticket_text},
        ],
        "status": "running",
        "pending": None,
        "final_answer": None,
    }
    return _advance(session_id)


def approve_pending(session_id: str, approved: bool) -> dict:
    session = _SESSIONS.get(session_id)
    if session is None:
        raise KeyError(f"Unknown session '{session_id}'")
    if session["status"] != "pending_approval":
        raise ValueError(f"Session '{session_id}' has no pending approval (status={session['status']})")

    pending = session["pending"]
    tool_call_id = pending["tool_call_id"]
    tool_name = _normalize_tool_name(pending["tool_name"])
    tool_args = pending["tool_args"]

    if tool_name not in TOOL_IMPLEMENTATIONS:
        session["status"] = "done"
        session["pending"] = None
        session["final_answer"] = (
            f"Agent attempted to call an unknown tool after approval: {pending['tool_name']}.")
        return _public_state(session_id)

    if approved:
        output = _execute_tool(session_id, tool_name, tool_args)
    else:
        output = {"rejected": True, "message": "Human reviewer rejected this action."}
        _log(session_id, tool_name, tool_args, None, status="rejected")

    session["messages"].append({
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": json.dumps(output),
    })

    # Re-queue any tool calls the model had batched alongside the destructive one
    for tc in pending.get("remaining_tool_calls", []):
        raw_name = tc["function"]["name"]
        name = _normalize_tool_name(raw_name)
        try:
            args = json.loads(tc["function"]["arguments"] or "{}")
        except json.JSONDecodeError:
            args = {}

        if name not in TOOL_IMPLEMENTATIONS:
            session["status"] = "done"
            session["pending"] = None
            session["final_answer"] = (
                f"Agent attempted to requeue an unknown tool: {raw_name}."
            )
            _log(session_id, raw_name, args, None, status="error", error="Unknown requeued tool call")
            return _public_state(session_id)

        if name in DESTRUCTIVE_TOOLS:
            session["status"] = "pending_approval"
            session["pending"] = {"tool_call_id": tc["id"], "tool_name": name, "tool_args": args,
                                    "remaining_tool_calls": []}
            _log(session_id, name, args, None, status="pending_approval")
            return _public_state(session_id)
        out = _execute_tool(session_id, name, args)
        session["messages"].append({"role": "tool", "tool_call_id": tc["id"], "content": json.dumps(out)})

    session["status"] = "running"
    session["pending"] = None
    return _advance(session_id)


def get_session(session_id: str) -> dict:
    if session_id not in _SESSIONS:
        raise KeyError(f"Unknown session '{session_id}'")
    return _public_state(session_id)


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Run the support agent from the terminal.")
    parser.add_argument("ticket_text", nargs="*", help="The ticket text for the agent.")
    parser.add_argument("--approve", action="store_true", help="Approve a pending destructive tool call.")
    parser.add_argument("--reject", action="store_true", help="Reject a pending destructive tool call.")
    parser.add_argument("--session-id", help="Session ID for approve/reject operations.")
    args = parser.parse_args()

    if args.approve or args.reject:
        if not args.session_id:
            raise SystemExit("--session-id is required when approving or rejecting.")
        result = approve_pending(args.session_id, approved=args.approve)
    else:
        if not args.ticket_text:
            raise SystemExit("Provide ticket text to run the agent.")
        ticket_text = " ".join(args.ticket_text)
        result = run_agent(ticket_text)

    print(json.dumps(result, indent=2, default=str))
