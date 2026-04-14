from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path


def _fallback_text_from_bytes(pdf_bytes: bytes) -> str:
    decoded = pdf_bytes.decode("latin-1", errors="ignore")
    chunks = re.findall(r"\(([^()]*)\)", decoded)
    if chunks:
        text = "\n".join(chunk.replace("\\n", "\n").replace("\\r", "") for chunk in chunks)
        return re.sub(r"\s+\n", "\n", text).strip()
    return decoded


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(BytesIO(pdf_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(page.strip() for page in pages if page.strip())
        if text.strip():
            return text
    except Exception:
        pass

    return _fallback_text_from_bytes(pdf_bytes)


def extract_text_from_pdf_file(pdf_path: Path) -> str:
    return extract_text_from_pdf_bytes(pdf_path.read_bytes())
