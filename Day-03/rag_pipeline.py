"""
rag_pipeline.py
----------------
Ties every step together:

  ingest(pdf_path)  -> load -> chunk -> embed -> store           (steps 1-3)
  ask(question)     -> embed question -> retrieve top 3          (step 4)
                        -> pass chunks to Groq -> grounded answer (step 5)

This is the only file that knows about all the pieces. Everything
else (pdf_loader, chunker, embedder, vector_store) is independently
testable and doesn't know about the others.
"""

from openai import OpenAI

import config
from chunker import chunk_pages
from embedder import Embedder
from pdf_loader import load_pdf
from vector_store import VectorStore


NO_ANSWER_PHRASE = "I don't know based on the provided document."

SYSTEM_PROMPT = (
    "You are a question-answering assistant. Answer ONLY using the "
    "context passages provided below, each labeled with its source page. "
    f"If the answer is not contained in the context, reply exactly: "
    f'"{NO_ANSWER_PHRASE}" '
    "Do not use outside knowledge. When you use a passage, mention which "
    "page it came from."
)


class RAGPipeline:
    def __init__(self) -> None:
        if not config.GROQ_API_KEY:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Put it in a .env file or export it "
                "as an environment variable before running."
            )
        self.embedder = Embedder()
        self.store = VectorStore(self.embedder)
        self.llm = OpenAI(api_key=config.GROQ_API_KEY, base_url=config.GROQ_BASE_URL)
        self.source_pdf: str | None = None

    # ---- Ingestion: steps 1-3 ------------------------------------------------
    def ingest(self, pdf_path: str) -> int:
        """
        Load a user-supplied PDF, chunk it, embed every chunk, and store
        the result in ChromaDB. Returns the number of chunks stored.
        """
        pages = load_pdf(pdf_path)
        chunks = chunk_pages(pages, chunk_size=config.CHUNK_SIZE, overlap=config.CHUNK_OVERLAP)
        if not chunks:
            raise RuntimeError("PDF produced no chunks -- nothing to index.")

        embeddings = self.embedder.embed([c.text for c in chunks])

        # Fresh PDF -> fresh collection, so old chunks from a previous
        # document never leak into answers for this one.
        self.store.reset()
        self.store.add_chunks(chunks, embeddings)

        self.source_pdf = pdf_path
        return len(chunks)

    # ---- Q&A: steps 4-5 -------------------------------------------------------
    def ask(self, question: str, top_k: int = config.TOP_K) -> dict:
        """
        Embed the question, retrieve the top_k most relevant chunks, and
        ask Groq to answer using only those chunks. Returns a dict with
        the answer text and the source chunks used, so the caller can
        show its work.
        """
        if self.store.count() == 0:
            raise RuntimeError("No document has been ingested yet. Call ingest() first.")

        question_embedding = self.embedder.embed([question])[0]
        hits = self.store.query(question_embedding, top_k=top_k)

        context = "\n\n".join(
            f"[Page {h['page']}]\n{h['text']}" for h in hits
        )
        user_prompt = f"Context passages:\n\n{context}\n\nQuestion: {question}"

        response = self.llm.chat.completions.create(
            model=config.GROQ_MODEL,
            max_tokens=config.MAX_ANSWER_TOKENS,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        answer = response.choices[0].message.content

        return {"answer": answer, "sources": hits}