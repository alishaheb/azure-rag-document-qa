"""Pure helper functions (no Azure calls). Easy to unit test."""
import hashlib
import io
import re

from pypdf import PdfReader


def extract_text(filename: str, data: bytes) -> str:
    """Get plain text from a PDF, TXT, or MD file."""
    name = filename.lower()
    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    if name.endswith((".txt", ".md")):
        return data.decode("utf-8", errors="replace")
    raise ValueError("Only .pdf, .txt and .md files are supported.")


def chunk_text(text: str, size: int = 1000, overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks of about `size` characters."""
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        # Try to end at a sentence or word boundary.
        if end < len(text):
            boundary = max(text.rfind(". ", start, end), text.rfind(" ", start, end))
            if boundary > start + size // 2:
                end = boundary + 1
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = end - overlap
    return [c for c in chunks if c]


def safe_key(*parts: str) -> str:
    """Azure AI Search keys allow only letters, digits, '_', '-' and '='."""
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def safe_filename(filename: str) -> str:
    name = filename.replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return name[:200] or "file"
