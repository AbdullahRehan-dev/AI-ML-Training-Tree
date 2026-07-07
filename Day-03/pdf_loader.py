"""
pdf_loader.py
-------------
Step 0 (not shown in the hands-on list, but a prerequisite for it):
turn a user-supplied PDF into plain text we can chunk.

Design choice: we keep page boundaries. Every chunk later carries a
"page" number in its metadata, so when the LLM answers we can say
*which page* the answer came from -- not just "some chunk somewhere".
That's the difference between "grounded" and "vaguely grounded".
"""

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


@dataclass
class Page:
    number: int       # 1-indexed, matches what a human would see in a PDF viewer
    text: str


class PDFLoadError(RuntimeError):
    """Raised when a PDF can't be read or contains no extractable text."""


def load_pdf(path: str | Path) -> list[Page]:
    """
    Read a PDF from disk and return its text, one entry per page.

    Works with any PDF a user hands you -- there is nothing hardcoded
    about the path or content here.
    """
    path = Path(path)
    if not path.exists():
        raise PDFLoadError(f"No such file: {path}")
    if path.suffix.lower() != ".pdf":
        raise PDFLoadError(f"Expected a .pdf file, got: {path.suffix}")

    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        raise PDFLoadError(f"Could not open '{path.name}' as a PDF: {exc}") from exc

    if reader.is_encrypted:
        # Try an empty password first (common for "restricted" but not
        # truly password-protected PDFs); otherwise fail loudly.
        try:
            reader.decrypt("")
        except Exception as exc:
            raise PDFLoadError(
                f"'{path.name}' is password-protected and could not be opened."
            ) from exc

    pages: list[Page] = []
    for i, raw_page in enumerate(reader.pages, start=1):
        text = (raw_page.extract_text() or "").strip()
        if text:
            pages.append(Page(number=i, text=text))

    if not pages:
        raise PDFLoadError(
            f"No extractable text found in '{path.name}'. "
            "It may be a scanned/image-only PDF (would need OCR, which "
            "this project does not do)."
        )

    return pages
