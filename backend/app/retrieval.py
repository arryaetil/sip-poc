"""Hybrid retrieval over the chunked corpus: keywords and meaning, fused by rank.

Two searches run over the same 1,104 chunks and are merged:

* **Keyword** reuses the tokeniser and scoring already in knowledge.py. It wins when
  the user's words appear in the document -- product names, "GeoNavigator", "DORA".
* **Vector** compares embeddings. It wins when they do not -- a Dutch question
  against an English passage that shares no vocabulary.

Neither is reliable alone. Measured on this corpus, an unrelated Dutch passage
scored 0.380 against a Dutch query while a genuinely related English passage scored
0.301: embeddings carry a same-language bias. Keyword search has the opposite flaw.
Fusing them treats agreement between two independent judges as the signal.

Fusion is Reciprocal Rank Fusion. Scores are discarded and only rank is used,
because BM25-style scores are unbounded while cosine sits in [-1, 1] -- adding them
lets one drown the other. Azure AI Search performs the same fusion server-side; see
MIGRATION.md for what comes out of this file when it does.

POC scope: vectors live in one file and every query compares against all of them.
At this corpus size that is milliseconds.
"""

from __future__ import annotations

from array import array
from dataclasses import dataclass
from functools import lru_cache
import json
import os
from pathlib import Path

from app.chunking import KnowledgeChunk, chunk_corpus
from app.embedding import EXPECTED_DIMENSIONS, embed_query, embed_texts
from app.knowledge import _tokens

# Conventional constant from the Reciprocal Rank Fusion paper. It damps the gap
# between first and second place, so one list cannot dominate on a single win.
RRF_K = 60
# How many results each half contributes before fusion.
CANDIDATES_PER_METHOD = 20


def vector_store_path() -> Path:
    configured = os.getenv("SIP_VECTOR_PATH", "").strip()
    if configured:
        return Path(configured)
    database = Path(os.getenv("SIP_DB_PATH", "")) if os.getenv("SIP_DB_PATH") else None
    directory = database.parent if database else Path(__file__).resolve().parent.parent / "data"
    return directory / "vectors.bin"


@dataclass(frozen=True)
class SearchResult:
    chunk: KnowledgeChunk
    score: float
    keyword_rank: int | None
    vector_rank: int | None


def build_vector_index(progress: bool = True) -> int:
    """Embed every chunk once and write the vectors to disk.

    Vectors are stored as raw float32 rather than JSON: 1,104 x 3072 numbers is
    about 13 MB packed, and roughly 80 MB as text. The chunk metadata goes beside
    it as JSON so the two can be read back together.
    """
    chunks = chunk_corpus()
    texts = [chunk.embedding_text for chunk in chunks]
    if progress:
        print(f"embedding {len(texts)} chunks...")

    vectors = embed_texts(texts)
    if vectors and len(vectors[0]) != EXPECTED_DIMENSIONS:
        raise RuntimeError(
            f"expected {EXPECTED_DIMENSIONS} dimensions, got {len(vectors[0])}. "
            "The embedding deployment changed; the stored index must be rebuilt."
        )

    path = vector_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    packed = array("f")
    for vector in vectors:
        packed.extend(vector)
    path.write_bytes(packed.tobytes())

    metadata = {
        "dimensions": len(vectors[0]) if vectors else 0,
        "count": len(chunks),
        "chunks": [
            {
                "chunk_id": c.chunk_id,
                "source_id": c.source_id,
                "document_title": c.document_title,
                "organisation": c.organisation,
                "language": c.language,
                "page_type": c.page_type,
                "canonical_url": c.canonical_url,
                "section": c.section,
                "heading": c.heading,
                "text": c.text,
            }
            for c in chunks
        ],
    }
    path.with_suffix(".json").write_text(json.dumps(metadata), encoding="utf-8")
    if progress:
        print(f"wrote {len(chunks)} vectors to {path} ({path.stat().st_size // 1024} KB)")
    return len(chunks)


@lru_cache(maxsize=1)
def load_vector_index() -> tuple[tuple[KnowledgeChunk, ...], tuple[array, ...]]:
    """Read the stored index. Raises if it has not been built yet."""
    path = vector_store_path()
    metadata_path = path.with_suffix(".json")
    if not path.exists() or not metadata_path.exists():
        raise FileNotFoundError(
            f"No vector index at {path}. Build it with build_vector_index()."
        )

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    dimensions = metadata["dimensions"]
    chunks = tuple(KnowledgeChunk(**entry) for entry in metadata["chunks"])

    packed = array("f")
    packed.frombytes(path.read_bytes())
    vectors = tuple(
        packed[index * dimensions : (index + 1) * dimensions] for index in range(len(chunks))
    )
    if len(vectors) != len(chunks):
        raise RuntimeError("vector file and metadata disagree; rebuild the index")
    return chunks, vectors


def _cosine(query: list[float], stored: array, query_magnitude: float) -> float:
    dot = sum(a * b for a, b in zip(query, stored))
    magnitude = sum(b * b for b in stored) ** 0.5
    return dot / (query_magnitude * magnitude) if magnitude else 0.0


def keyword_ranking(query: str, chunks: tuple[KnowledgeChunk, ...]) -> list[int]:
    """Rank chunks by literal word overlap, reusing the existing tokeniser."""
    query_tokens = set(_tokens(query))
    if query_tokens - {"ibc", "group"}:
        query_tokens -= {"ibc", "group"}
    if not query_tokens:
        return []

    scored: list[tuple[float, int]] = []
    for index, chunk in enumerate(chunks):
        haystack = _tokens(f"{chunk.heading} {chunk.section} {chunk.text}")
        if not haystack:
            continue
        hits = sum(1 for token in haystack if token in query_tokens)
        if not hits:
            continue
        # Divide by length so a long chunk does not win purely by being long.
        scored.append((hits / (len(haystack) ** 0.5), index))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [index for _, index in scored[:CANDIDATES_PER_METHOD]]


def vector_ranking(query: str, vectors: tuple[array, ...]) -> list[int]:
    """Rank chunks by closeness in meaning."""
    query_vector = embed_query(query)
    query_magnitude = sum(a * a for a in query_vector) ** 0.5
    if not query_magnitude:
        return []
    scored = [
        (_cosine(query_vector, stored, query_magnitude), index)
        for index, stored in enumerate(vectors)
    ]
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [index for _, index in scored[:CANDIDATES_PER_METHOD]]


def hybrid_search(query: str, limit: int = 5) -> list[SearchResult]:
    """Run both searches and fuse them by rank."""
    chunks, vectors = load_vector_index()
    keyword = keyword_ranking(query, chunks)
    semantic = vector_ranking(query, vectors)

    positions: dict[int, dict[str, int]] = {}
    for rank, index in enumerate(keyword, start=1):
        positions.setdefault(index, {})["keyword"] = rank
    for rank, index in enumerate(semantic, start=1):
        positions.setdefault(index, {})["vector"] = rank

    results = [
        SearchResult(
            chunk=chunks[index],
            # Only rank contributes. A document absent from one list simply gains
            # nothing from it, rather than being penalised.
            score=sum(1 / (RRF_K + rank) for rank in ranks.values()),
            keyword_rank=ranks.get("keyword"),
            vector_rank=ranks.get("vector"),
        )
        for index, ranks in positions.items()
    ]
    results.sort(key=lambda result: (-result.score, result.chunk.chunk_id))
    return results[:limit]
