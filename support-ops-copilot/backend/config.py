"""
Centralized config. Everything that might change between a laptop, a CI
runner, and a deployed box lives here, read once from the environment.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root regardless of where uvicorn is launched from
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROK_MODEL = os.getenv("GROK_MODEL", "openai/gpt-oss-20b")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.7"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

CHROMA_PERSIST_DIR = str(ROOT_DIR / os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db").lstrip("./"))
KNOWLEDGE_DOCS_DIR = ROOT_DIR / "backend" / "knowledge_base" / "docs"

LOGS_DIR = ROOT_DIR / "backend" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
TOOL_CALL_LOG_PATH = LOGS_DIR / "tool_call_log.jsonl"

if not GROQ_API_KEY:
    # Don't crash on import (so `python -m backend.knowledge_base.ingest` etc.
    # still works without a key) but make it loud when someone actually needs it.
    import warnings
    warnings.warn(
        "GROQ_API_KEY is not set. Copy .env.example to .env and add your Grok key."
    )




