"""
config.py
---------
Central place for every tunable constant in the system.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file explicitly from the same directory as this file
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

DB_DIR = Path(__file__).parent / "chroma_db"
COLLECTION_NAME = "pdf_chunks"

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150

TOP_K = 3

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
MAX_ANSWER_TOKENS = 1000