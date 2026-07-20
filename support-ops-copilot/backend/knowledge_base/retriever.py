"""
Stage 3 - Give It Knowledge (RAG), query half.

retrieve() pulls top-k chunks from ChromaDB for a question.
answer_from_knowledge_base() then asks Grok to answer USING ONLY those
chunks, and every answer must cite which chunk/doc it came from - if
retrieval comes back empty or irrelevant, we say so instead of letting the
model free-associate (see BREAKING_IT.md case #3).
"""
from __future__ import annotations
import functools

import chromadb
from chromadb.utils import embedding_functions

from backend import config
from backend.schemas import RAGAnswer, Citation
from backend.reliability import call_structured
from backend.knowledge_base.ingest import COLLECTION_NAME, EMBEDDING_MODEL


@functools.lru_cache(maxsize=1)
def _get_collection() -> chromadb.Collection:
    chroma_client = chromadb.PersistentClient(path=config.CHROMA_PERSIST_DIR)
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
    try:
        return chroma_client.get_collection(name=COLLECTION_NAME, embedding_function=embed_fn)
    except Exception as e:
        raise RuntimeError(
            "Knowledge base index not found. Run `python -m backend.knowledge_base.ingest` first."
        ) from e


def retrieve(question: str, top_k: int = 3) -> list[dict]:
    collection = _get_collection()
    results = collection.query(query_texts=[question], n_results=top_k)

    hits = []
    ids = results.get("ids", [[]])[0]
    docs = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    for chunk_id, doc, meta, dist in zip(ids, docs, metadatas, distances):
        hits.append({"chunk_id": chunk_id, "text": doc, "metadata": meta, "distance": dist})
    return hits


RAG_SYSTEM = """You are a support assistant answering a question using ONLY
the knowledge base excerpts provided below. Every claim in your answer must
be traceable to one of these excerpts - never add information you know from
elsewhere. If the excerpts don't actually answer the question, say so
honestly in the answer field and lower your confidence accordingly, rather
than guessing. In `citations`, list every chunk_id you actually relied on,
with the exact `source` name and a short supporting `snippet` copied from
that chunk."""


def answer_from_knowledge_base(question: str, top_k: int = 3) -> RAGAnswer:
    hits = retrieve(question, top_k=top_k)

    if not hits:
        return RAGAnswer(
            answer="I don't have information on that in the knowledge base.",
            citations=[],
            confidence=0.1,
        )

    excerpts_block = "\n\n".join(
        f"[chunk_id: {h['chunk_id']}] (source: {h['metadata']['source']})\n{h['text']}"
        for h in hits
    )
    user_prompt = f"Question: {question}\n\nKnowledge base excerpts:\n{excerpts_block}"

    result = call_structured(RAG_SYSTEM, user_prompt, RAGAnswer, temperature=0.2)

    # Belt-and-suspenders: drop any citation that names a chunk_id we didn't
    # actually retrieve, so the UI never shows a source we can't back up.
    valid_ids = {h["chunk_id"] for h in hits}
    result.citations = [c for c in result.citations if c.chunk_id in valid_ids]
    if not result.citations and result.confidence > 0.3:
        # Model claimed an answer but didn't properly cite - don't let that
        # look more trustworthy than it is.
        result.confidence = min(result.confidence, 0.3)

    return result


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Query the knowledge base from the terminal.")
    parser.add_argument("question", nargs="+", help="The question to ask the knowledge base.")
    parser.add_argument("--top-k", type=int, default=3, help="Number of top chunks to retrieve.")
    args = parser.parse_args()

    question = " ".join(args.question)
    result = answer_from_knowledge_base(question, top_k=args.top_k)
    print(json.dumps(result.model_dump(), indent=2, default=str))
