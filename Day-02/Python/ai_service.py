import os
import re
import json
import time
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()  # reads GROQ_API_KEY from .env into the environment

groq = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

MODEL = "llama-3.3-70b-versatile"
MAX_RETRIES = 3
CONFIDENCE_THRESHOLD = 0.7  # below this -> flagged for human review


def clean_json_string(raw: str) -> str:
    """Strips markdown code fences (```json ... ```) that models sometimes
    add even when told not to."""
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"```\s*$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def validate_shape(obj, required_keys):
    """Returns an error string if `obj` doesn't match the expected shape,
    or None if it's valid."""
    if not isinstance(obj, dict):
        return "Response is not a JSON object"

    for key in required_keys:
        if key not in obj:
            return f'Missing required key: "{key}"'

    if "confidence" in obj:
        c = obj["confidence"]
        if not isinstance(c, (int, float)) or isinstance(c, bool) or not (0 <= c <= 1):
            return f'"confidence" must be a number between 0 and 1, got: {c!r}'

    return None


def call_groq_json(system_prompt: str, user_prompt: str, required_keys: list, temperature: float = 0.3) -> dict:
    """Core helper: calls Groq, parses + validates the JSON response, and
    retries up to MAX_RETRIES times on network errors, malformed JSON, or
    schema validation failures. Adds `needs_human_review` based on
    model-reported confidence before returning.

    Raises RuntimeError only after all retries are exhausted — callers
    should wrap calls in try/except and decide how to handle a hard
    failure (queue for manual processing, alert, etc).
    """
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = groq.chat.completions.create(
                model=MODEL,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )

            raw = response.choices[0].message.content
            cleaned = clean_json_string(raw)

            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError as parse_err:
                raise ValueError(
                    f"JSON parse failed: {parse_err}. Raw output: {raw[:200]}"
                )

            validation_error = validate_shape(parsed, required_keys)
            if validation_error:
                raise ValueError(f"Schema validation failed: {validation_error}")

            # Defensive default in case the model omits confidence despite instructions
            if not isinstance(parsed.get("confidence"), (int, float)):
                parsed["confidence"] = 0.5

            parsed["needs_human_review"] = parsed["confidence"] < CONFIDENCE_THRESHOLD
            parsed["_meta"] = {"attempts": attempt}

            return parsed

        except Exception as err:
            last_error = err
            print(f"[call_groq_json] Attempt {attempt}/{MAX_RETRIES} failed: {err}")
            if attempt < MAX_RETRIES:
                backoff_seconds = 0.5 * (2 ** (attempt - 1))  # 0.5s, 1s, 2s
                time.sleep(backoff_seconds)

    raise RuntimeError(
        f"call_groq_json failed after {MAX_RETRIES} attempts. Last error: {last_error}"
    )


# 1. Lead qualification
def qualify_lead(lead_info: str) -> dict:
    system = """You are a B2B sales assistant. Given raw lead info, score the lead
from 1-10 on purchase likelihood and give a one-sentence reason.
Respond ONLY with valid JSON (no markdown, no explanation) matching exactly this shape:
{
  "score": <integer 1-10>,
  "reason": "<one sentence>",
  "confidence": <number 0-1, how confident you are in this score>
}"""
    return call_groq_json(system, lead_info, ["score", "reason", "confidence"])


# 2. Support ticket classifier
def classify_ticket(ticket_text: str) -> dict:
    system = """You are a support ticket classifier. Classify the ticket into
exactly one category: Billing, Technical, Account, or General.
Also assign urgency: Low, Medium, or High.
Respond ONLY with valid JSON (no markdown, no explanation) matching exactly this shape:
{
  "category": "<Billing|Technical|Account|General>",
  "urgency": "<Low|Medium|High>",
  "confidence": <number 0-1, how confident you are in this classification>
}"""
    return call_groq_json(system, ticket_text, ["category", "urgency", "confidence"])


# 3. Email drafter
def draft_email(recipient: str, purpose: str, tone: str = "professional") -> dict:
    system = f"""You are an email drafting assistant. Write a {tone} email under
120 words.
Respond ONLY with valid JSON (no markdown, no explanation) matching exactly this shape:
{{
  "subject": "<subject line>",
  "body": "<email body, under 120 words>",
  "confidence": <number 0-1, how confident you are this email fits the purpose well>
}}"""
    user = f"Recipient: {recipient}\nPurpose: {purpose}"
    return call_groq_json(system, user, ["subject", "body", "confidence"], temperature=0.6)


# 4. Data extractor from raw text
def extract_data(raw_text: str) -> dict:
    system = """Extract structured data from the text.
Respond ONLY with valid JSON (no markdown, no explanation) matching exactly this shape:
{
  "name": <string or null>,
  "email": <string or null>,
  "phone": <string or null>,
  "company": <string or null>,
  "confidence": <number 0-1, how confident you are in the extracted fields>
}
Use null for any field not found in the text."""
    return call_groq_json(
        system, raw_text, ["name", "email", "phone", "company", "confidence"], temperature=0
    )
