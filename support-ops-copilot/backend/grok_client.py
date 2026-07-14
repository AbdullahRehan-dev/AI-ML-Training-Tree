"""
Grok speaks the OpenAI Chat Completions schema, so we reuse the `openai`
python package and just point it at the Grok Cloud base URL. One shared client,
imported everywhere else that needs to talk to the model.
"""
from openai import OpenAI
from backend import config

if not config.GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY must be set in .env before running the app.")

client = OpenAI(api_key=config.GROQ_API_KEY, base_url=config.GROQ_BASE_URL)

DEFAULT_MODEL = config.GROK_MODEL
