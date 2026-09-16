"""Split the knowledge corpus into passages that can each answer a question alone.

A chunk is the unit that gets embedded and retrieved. The test it has to pass is
simple: if this passage were the only thing the model saw, could it answer and be
cited for it? That rules out both extremes -- a bare heading says nothing, and a
whole page averages six different topics into one meaningless vector.

Splitting happens on the document's own headings rather than on a word count,
because the author already grouped the ideas. A blind cut every N words lands
between a heading and its description, or halfway across two capabilities.

POC scope: sizes are measured in characters, not tokens, to avoid a tokeniser
dependency. See MIGRATION.md before moving this to Azure AI Search, which performs
the equivalent split server-side with its own Split skill.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from app.knowledge import KnowledgeDocument, load_knowledge_documents

# ~1200 characters is roughly 300 tokens: comfortably one idea, small enough that
# the embedding stays sharp. Only reached by unusually long sections.
MAX_CHUNK_CHARACTERS = 1_200
# Below this a passage carries too little meaning to retrieve on its own, so it is
# folded into its section intro instead of becoming a chunk.
MIN_CHUNK_CHARACTERS = 40

BLOCK_SPLIT = re.compile(r"\n{2,}")

# Layout labels and numbering the extractor carried over from the page furniture.
# They sit between headings as if they were body text, so without this they become
# chunks whose entire content is the word "FAQ". knowledge.py skips the same
# markers when it structures a page; keep the two lists in step.
LAYOUT_MARKERS = {
    "context",
    "customer solution case",
    "faq",
    "hoe het werkt in de praktijk",
    "veelgestelde vragen",
    "wat was het probleem",
    "what was the problem",
}


def _is_layout_artifact(block: str) -> bool:
    text = block.strip().rstrip("?:.").casefold()
    return text in LAYOUT_MARKERS or text.isdigit()


@dataclass(frozen=True)
class KnowledgeChunk:
    """One retrievable passage, carrying the identity of where it came from.

    `text` is what gets embedded. Everything else travels alongside it so the
    passage can be cited as [Source N] and filtered on without re-reading the
    document -- a chunk retrieved on its own must still be able to say which
    offering it describes and whose it is.
    """

    chunk_id: str
    source_id: str
    document_title: str
    organisation: str
    language: str
    page_type: str
    canonical_url: str
    section: str
    heading: str
    text: str
    visibility: str = "org"
    owner_id: str | None = None
    upload_id: str | None = None

    @property
    def embedding_text(self) -> str:
        """The passage with its context restored.

        "Find knowledge quickly instead of searching endlessly" is not retrievable
        on its own -- it never says which service or whose. Prefixing the document
        and section headings puts that meaning back into the vector.
        """
        trail = " > ".join(part for part in (self.section, self.heading) if part)
        header = f"{self.document_title} ({self.organisation})"
        return f"{header}\n{trail}\n\n{self.text}" if trail else f"{header}\n\n{self.text}"


def _heading_level(block: str) -> int:
    match = re.match(r"(#{1,6})\s", block)
    return len(match.group(1)) if match else 0


def _clean(block: str) -> str:
    return block.lstrip("#").strip().rstrip(":")


def _split_oversized(paragraphs: list[str]) -> list[str]:
    """Group paragraphs into passages under the size budget.

    Splitting only ever happens at a paragraph boundary. A single paragraph longer
    than the budget is kept whole: cutting mid-sentence would damage the meaning
    the embedding is supposed to capture, which is worse than an oversized chunk.
    """
    passages: list[str] = []
    current: list[str] = []
    length = 0
    for paragraph in paragraphs:
        if current and length + len(paragraph) > MAX_CHUNK_CHARACTERS:
            passages.append("\n\n".join(current))
            current, length = [], 0
        current.append(paragraph)
        length += len(paragraph) + 2
    if current:
        passages.append("\n\n".join(current))
    return passages


def chunk_text_document(
    *,
    source_id: str,
    title: str,
    content: str,
    organisation: str = "Uploaded document",
    language: str = "unknown",
    page_type: str = "upload",
    canonical_url: str = "",
    visibility: str = "org",
    owner_id: str | None = None,
    upload_id: str | None = None,
) -> tuple[KnowledgeChunk, ...]:
    """Split any text source while preserving retrieval visibility metadata."""
    blocks = [block.strip() for block in BLOCK_SPLIT.split(content) if block.strip()]

    chunks: list[KnowledgeChunk] = []
    section = ""
    heading = ""
    body: list[str] = []

    def flush() -> None:
        nonlocal body
        text_blocks = [block for block in body if block]
        body = []
        if not text_blocks:
            # A heading with no text beneath it. On these sites that is a logo tile
            # or a contact card -- a name with no content. Embedding it would add a
            # vector that means almost nothing and competes for a place in the
            # results, so it is deliberately not a chunk.
            return
        for passage in _split_oversized(text_blocks):
            if len(passage) < MIN_CHUNK_CHARACTERS and chunks and chunks[-1].heading == heading:
                continue
            chunks.append(
                KnowledgeChunk(
                    chunk_id=f"{source_id}#{len(chunks):03d}",
                    source_id=source_id,
                    document_title=title,
                    organisation=organisation,
                    language=language,
                    page_type=page_type,
                    canonical_url=canonical_url,
                    section=section,
                    heading=heading,
                    text=passage,
                    visibility=visibility,
                    owner_id=owner_id,
                    upload_id=upload_id,
                )
            )

    for block in blocks:
        level = _heading_level(block)
        if level == 0:
            if not _is_layout_artifact(block):
                body.append(block)
            continue
        flush()
        if level <= 2:
            # A new top-level section resets the item heading beneath it.
            section = _clean(block)
            heading = ""
        else:
            heading = _clean(block)
    flush()
    return tuple(chunks)


def chunk_document(document: KnowledgeDocument) -> tuple[KnowledgeChunk, ...]:
    """Split one reviewed website document into organisation-wide chunks."""
    return chunk_text_document(
        source_id=document.source_id,
        title=document.title,
        content=document.content,
        organisation=document.organisation,
        language=document.language,
        page_type=document.page_type,
        canonical_url=document.canonical_url,
    )


def chunk_corpus() -> tuple[KnowledgeChunk, ...]:
    """Split every indexed document in the corpus."""
    return tuple(
        chunk for document in load_knowledge_documents() for chunk in chunk_document(document)
    )
