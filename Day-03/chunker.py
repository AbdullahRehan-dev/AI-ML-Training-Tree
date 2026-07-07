"""
chunker.py
----------
Step 1: "Chunk a PDF into pieces."

We split on paragraph/sentence boundaries where possible instead of
slicing blindly at N characters, so a chunk doesn't end mid-sentence
if we can help it. Consecutive chunks overlap slightly so an idea
that spans a chunk boundary isn't lost to either side.
"""

import re
from dataclasses import dataclass

from pdf_loader import Page


@dataclass
class Chunk:
    id: str
    text: str
    page: int  # which PDF page this chunk came from


def _split_into_sentences(text: str) -> list[str]:
    # Good enough for this purpose -- not a full NLP sentence tokenizer,
    # just splits after ., ?, ! followed by whitespace.
    sentences = re.split(r"(?<=[.?!])\s+", text.strip())
    return [s for s in sentences if s]


def chunk_pages(
    pages: list[Page],
    chunk_size: int = 800,
    overlap: int = 150,
) -> list[Chunk]:
    """
    Turn a list of (page_number, page_text) into overlapping chunks.

    Chunks never cross a page boundary -- keeping that boundary clean
    is what lets us cite "page 4" instead of "somewhere in the document".
    """
    chunks: list[Chunk] = []
    running_id = 0

    for page in pages:
        sentences = _split_into_sentences(page.text)
        current = ""

        for sentence in sentences:
            # If adding this sentence would blow past chunk_size, close
            # the current chunk out and start a new one that begins with
            # the tail of the previous chunk (the "overlap").
            if current and len(current) + len(sentence) + 1 > chunk_size:
                chunks.append(Chunk(id=f"chunk_{running_id}", text=current.strip(), page=page.number))
                running_id += 1
                tail = current[-overlap:] if overlap else ""
                current = f"{tail} {sentence}".strip()
            else:
                current = f"{current} {sentence}".strip()

        if current:
            chunks.append(Chunk(id=f"chunk_{running_id}", text=current.strip(), page=page.number))
            running_id += 1

    return chunks
