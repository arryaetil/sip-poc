from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import re

from docx import Document
from pypdf import PdfReader


MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 200
ALLOWED_MEDIA_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}


@dataclass(frozen=True)
class ExtractedUpload:
    text: str
    page_count: int | None


def safe_filename(filename: str, media_type: str) -> str:
    expected_suffix = ALLOWED_MEDIA_TYPES.get(media_type)
    if expected_suffix is None:
        raise ValueError("Only PDF and DOCX files are allowed.")
    name = Path(filename).name
    if Path(name).suffix.casefold() != expected_suffix:
        raise ValueError("The file extension does not match its media type.")
    stem = re.sub(r"[^A-Za-z0-9._ -]+", "-", Path(name).stem).strip(" .-") or "document"
    return f"{stem[:120]}{expected_suffix}"


def extract_text(data: bytes, media_type: str) -> ExtractedUpload:
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("The file exceeds the 10 MB upload limit.")
    if media_type == "application/pdf":
        reader = PdfReader(BytesIO(data))
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ValueError("The PDF exceeds the 200-page limit.")
        pages = []
        for number, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append(f"## Page {number}\n\n{text}")
        result = ExtractedUpload("\n\n".join(pages), len(reader.pages))
    elif media_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        document = Document(BytesIO(data))
        paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
        result = ExtractedUpload("\n\n".join(paragraphs), None)
    else:
        raise ValueError("Only PDF and DOCX files are allowed.")
    if not result.text.strip():
        raise ValueError("No readable text was found in the document.")
    return result
