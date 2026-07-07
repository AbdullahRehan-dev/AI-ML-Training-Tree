"""
main.py
-------
Command-line front end for the whole pipeline.

Usage:
    python main.py path/to/your.pdf
    python main.py                     # will prompt you for a path

Then ask questions in a loop until you type 'exit'.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env file explicitly from the same directory as this file
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

from pdf_loader import PDFLoadError
from rag_pipeline import RAGPipeline


def get_pdf_path_from_args_or_prompt() -> str:
    if len(sys.argv) > 1:
        return sys.argv[1]
    path = input("Path to your PDF: ").strip().strip('"')
    return path


def main() -> None:
    print("=== Mini RAG System ===\n")

    pdf_path = get_pdf_path_from_args_or_prompt()

    try:
        pipeline = RAGPipeline()
    except RuntimeError as exc:
        print(f"Setup error: {exc}")
        sys.exit(1)

    print(f"\nIngesting '{Path(pdf_path).name}' ...")
    try:
        num_chunks = pipeline.ingest(pdf_path)
    except PDFLoadError as exc:
        print(f"Could not process PDF: {exc}")
        sys.exit(1)

    print(f"Done. Indexed {num_chunks} chunks into ChromaDB.\n")
    print("Ask a question about the document (type 'exit' to quit,")
    print("or 'load <path>' to switch to a different PDF).\n")

    while True:
        question = input("> ").strip()
        if not question:
            continue
        if question.lower() in {"exit", "quit"}:
            break

        if question.lower().startswith("load "):
            new_path = question[5:].strip().strip('"')
            try:
                num_chunks = pipeline.ingest(new_path)
                print(f"Loaded '{Path(new_path).name}' -- {num_chunks} chunks indexed.\n")
            except PDFLoadError as exc:
                print(f"Could not process PDF: {exc}\n")
            continue

        try:
            result = pipeline.ask(question)
        except RuntimeError as exc:
            print(f"Error: {exc}\n")
            continue
        except Exception as exc:  # network/API errors, etc.
            print(f"Something went wrong calling the LLM: {exc}\n")
            continue

        print(f"\n{result['answer']}\n")
        print("Sources:")
        for i, src in enumerate(result["sources"], start=1):
            # Clean up the text: remove extra whitespace and limit length
            text = src["text"].strip()
            text = " ".join(text.split())  # Normalize whitespace
            preview = text[:150]  # Increase preview length
            if len(text) > 150:
                preview += "..."
            print(f"  [{i}] page {src['page']}: \"{preview}\"")
        print()


if __name__ == "__main__":
    main()
