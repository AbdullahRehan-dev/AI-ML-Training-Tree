"""
vector_store.py
----------------
Step 3: "Store in ChromaDB locally."
Step 4: "Search with a question and retrieve top 3 chunks."

A thin wrapper around a persistent Chroma collection. Keeping this in
its own class means rag_pipeline.py doesn't need to know anything
about Chroma's API -- just "add these chunks" and "give me the top k
matches for this question".
"""

import chromadb

import config
from chunker import Chunk
from embedder import Embedder


class VectorStore:
    def __init__(self, embedder: Embedder, collection_name: str = config.COLLECTION_NAME):
        self._client = chromadb.PersistentClient(path=str(config.DB_DIR))
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=embedder.chroma_embedding_function,
            metadata={"hnsw:space": "cosine"},
        )

    def reset(self) -> None:
        """Wipe the collection -- useful when swapping in a new PDF."""
        self._client.delete_collection(self._collection.name)
        self._collection = self._client.get_or_create_collection(
            name=self._collection.name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        if not chunks:
            return
        self._collection.add(
            ids=[c.id for c in chunks],
            documents=[c.text for c in chunks],
            embeddings=embeddings,
            metadatas=[{"page": c.page} for c in chunks],
        )

    def count(self) -> int:
        return self._collection.count()

    def query(self, question_embedding: list[float], top_k: int = config.TOP_K) -> list[dict]:
        """
        Return the top_k most similar chunks to the question, each as
        {"text": ..., "page": ..., "distance": ...} sorted best-first.
        """
        n = min(top_k, self.count())
        if n == 0:
            return []

        result = self._collection.query(
            query_embeddings=[question_embedding],
            n_results=n,
        )

        hits = []
        for text, meta, dist in zip(
            result["documents"][0], result["metadatas"][0], result["distances"][0]
        ):
            hits.append({"text": text, "page": meta.get("page"), "distance": dist})
        return hits
