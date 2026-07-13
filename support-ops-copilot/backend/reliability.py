"""
Stage 2 - Make It Production-Safe.

Free-text model output can't be trusted directly, so every AIService call
goes through `call_structured`:
  1. Ask Grok for JSON matching a schema (with the schema shown in-prompt).
  2. Try to parse + validate it with the corresponding Pydantic model.
  3. If it fails validation, retry (max_retries) with the validation error
     fed back to the model so it can correct itself.
  4. If it still fails after all retries, fail gracefully: return a
     zero-confidence fallback instead of crashing the request.
"""
from __future__ import annotations
import json
import logging
from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError

from backend import config
from backend.grok_client import client, DEFAULT_MODEL
from backend.schemas import ReviewFlag

logger = logging.getLogger("reliability")

T = TypeVar("T", bound=BaseModel)


class StructuredGenerationError(Exception):
    """Raised when the model could not produce valid JSON after all retries."""

    def __init__(self, message: str, last_raw_output: str = ""):
        super().__init__(message)
        self.last_raw_output = last_raw_output


def call_structured(
    system_prompt: str,
    user_prompt: str,
    schema: Type[T],
    max_retries: int | None = None,
    temperature: float = 0.3,
) -> T:
    """Call Grok and coerce the response into `schema`, retrying on failure."""
    max_retries = max_retries if max_retries is not None else config.MAX_RETRIES

    schema_hint = (
        f"Respond with ONLY a single JSON object (no markdown fences, no "
        f"preamble) matching this JSON schema exactly:\n{schema.model_json_schema()}"
    )
    messages = [
        {"role": "system", "content": f"{system_prompt}\n\n{schema_hint}"},
        {"role": "user", "content": user_prompt},
    ]

    last_error: Exception | None = None
    last_raw = ""

    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"},
                max_tokens=800,
            )
            raw = response.choices[0].message.content or ""
            last_raw = raw
            data = json.loads(raw)
            return schema.model_validate(data)

        except (json.JSONDecodeError, ValidationError) as e:
            last_error = e
            logger.warning("Attempt %d/%d failed validation: %s", attempt, max_retries, e)
            # Feed the failure back so the model can self-correct next try
            messages.append({"role": "assistant", "content": last_raw})
            messages.append({
                "role": "user",
                "content": (
                    f"That response was invalid JSON or didn't match the schema. "
                    f"Error: {e}. Return ONLY the corrected JSON object, nothing else."
                ),
            })
        except Exception as e:  # network errors, rate limits, etc.
            last_error = e
            logger.warning("Attempt %d/%d failed with API error: %s", attempt, max_retries, e)

    # Fail gracefully rather than raising 500s all over the app.
    raise StructuredGenerationError(
        f"Failed to get valid {schema.__name__} after {max_retries} attempts: {last_error}",
        last_raw_output=last_raw,
    )


def build_review_flag(confidence: float, context: str = "") -> ReviewFlag:
    """Stage 2: flag anything under the confidence threshold for human review."""
    flagged = confidence < config.CONFIDENCE_THRESHOLD
    reason = (
        f"Confidence {confidence:.2f} is below threshold {config.CONFIDENCE_THRESHOLD:.2f}"
        if flagged
        else f"Confidence {confidence:.2f} meets threshold {config.CONFIDENCE_THRESHOLD:.2f}"
    )
    if context:
        reason = f"{reason} ({context})"
    return ReviewFlag(
        flagged=flagged,
        threshold=config.CONFIDENCE_THRESHOLD,
        confidence=confidence,
        reason=reason,
    )
