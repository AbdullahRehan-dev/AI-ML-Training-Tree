"""
embedder.py
-----------
Step 2: "Generate embeddings for each chunk."

We use Chroma's built-in embedding function (all-MiniLM-L6-v2, run
locally through onnxruntime). Two deliberate design choices here:

1. It runs fully offline/locally after the first download -- no API
   calls, no per-token cost, no rate limits for the embedding step.
2. It avoids pulling in a full PyTorch install just to embed text,
   which keeps the project's dependency footprint (and install time)
   small. If you later want a stronger embedding model, swap the
   embedding function in `_load_embedding_function()` -- everything
   else in the pipeline is agnostic to which one you use.

We wrap it in our own class so "generate embeddings" is an explicit,
visible step in the pipeline rather than something buried inside
Chroma's `.add()` call.
"""

from chromadb.utils import embedding_functions


class Embedder:
    def __init__(self) -> None:
        self._fn = embedding_functions.DefaultEmbeddingFunction()

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Turn a list of strings into a list of embedding vectors."""
        if not texts:
            return []
        return self._fn(texts)

    @property
    def chroma_embedding_function(self):
        """
        Expose the underlying Chroma-compatible embedding function so
        the collection can also embed *queries* the same way at search
        time (queries and documents must use the same embedding space).
        """
        return self._fn
