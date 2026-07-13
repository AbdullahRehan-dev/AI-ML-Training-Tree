"""
Stage 3 - Give It Knowledge (RAG), ingestion half.

Chunks the markdown docs in knowledge_base/docs/, embeds them locally with
sentence-transformers (no API cost/latency for embeddings - Grok is only
used for the final grounded generation), and stores vectors in a persistent
local ChromaDB collection.

Run directly to (re)build the index:
    python -m backend.knowledge_base.ingest
"""
from __future__ import annotations
import re
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

from backend import config

COLLECTION_NAME = "support_kb"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def chunk_markdown(text: str, source: str, max_chars: int = 700) -> list[dict]:
    """
    Split on '## ' headers first (each section is a self-contained topic),
    then further split any section that's still too long. Keeps chunks
    topically coherent instead of cutting mid-thought at a fixed char count.
    """
    sections = re.split(r"\n(?=## )", text.strip())
    chunks = []
    for section in sections:
        section = section.strip()
        # Skip the leading "# Doc Title" sliver before the first "## " section
        # - it carries no retrievable content on its own.
        if not section or len(section) < 40:
            continue
        header_match = re.match(r"##\s+(.+)", section)
        title = header_match.group(1).strip() if header_match else source

        if len(section) <= max_chars:
            chunks.append({"text": section, "title": title})
        else:
            # Fall back to paragraph-level splitting for long sections
            paragraphs = section.split("\n\n")
            buf = ""
            for para in paragraphs:
                if len(buf) + len(para) + 2 <= max_chars:
                    buf = f"{buf}\n\n{para}" if buf else para
                else:
                    if buf:
                        chunks.append({"text": buf, "title": title})
                    buf = para
            if buf:
                chunks.append({"text": buf, "title": title})
    return chunks


def build_index(persist_dir: str | None = None) -> chromadb.Collection:
    persist_dir = persist_dir or config.CHROMA_PERSIST_DIR
    Path(persist_dir).mkdir(parents=True, exist_ok=True)

    chroma_client = chromadb.PersistentClient(path=persist_dir)
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)

    # Rebuild clean each time so re-running ingest never leaves stale/duplicate chunks
    try:
        chroma_client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = chroma_client.create_collection(name=COLLECTION_NAME, embedding_function=embed_fn)

    ids, docs, metadatas = [], [], []
    doc_paths = sorted(config.KNOWLEDGE_DOCS_DIR.glob("*.md"))
    for doc_path in doc_paths:
        text = doc_path.read_text(encoding="utf-8")
        chunks = chunk_markdown(text, source=doc_path.stem)
        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc_path.stem}::chunk{i}"
            ids.append(chunk_id)
            docs.append(chunk["text"])
            metadatas.append({"source": doc_path.stem, "title": chunk["title"], "chunk_index": i})

    if ids:
        collection.add(ids=ids, documents=docs, metadatas=metadatas)

    print(f"Indexed {len(ids)} chunks from {len(doc_paths)} docs into '{persist_dir}'")
    return collection


if __name__ == "__main__":
    build_index()
