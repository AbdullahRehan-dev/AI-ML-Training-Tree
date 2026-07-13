#!/usr/bin/env bash
# Creates a Python 3.12 venv, installs deps, and builds the RAG index.
# Usage: bash scripts/setup.sh
set -e

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-python3.12}"
if ! command -v "$PYTHON_BIN" &> /dev/null; then
    echo "python3.12 not found, falling back to python3 (check your version with python3 --version)"
    PYTHON_BIN="python3"
fi

echo "==> Creating venv with $PYTHON_BIN"
"$PYTHON_BIN" -m venv venv

echo "==> Activating venv"
source venv/bin/activate

echo "==> Upgrading pip"
pip install --upgrade pip

echo "==> Installing requirements"
pip install -r requirements.txt

if [ ! -f .env ]; then
    echo "==> Creating .env from .env.example - add your GROQ_API_KEY before running the app"
    cp .env.example .env
fi

echo "==> Building the RAG knowledge base index"
python -m backend.knowledge_base.ingest

echo ""
echo "Setup complete."
echo "1. Edit .env and add your GROQ_API_KEY"
echo "2. source venv/bin/activate"
echo "3. uvicorn backend.main:app --reload --port 8000"
echo "4. Open frontend/index.html in your browser (or serve it, see README)"
