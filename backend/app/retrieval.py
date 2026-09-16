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
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
import json
import logging
import math
import os
from pathlib import Path

from app.chunking import KnowledgeChunk, chunk_corpus, chunk_text_document
from app.embedding import EXPECTED_DIMENSIONS, embed_query, embed_texts
from app.knowledge import (
    _tokens,
    create_excerpt,
    get_knowledge_document,
    search_knowledge,
)

# Conventional constant from the Reciprocal Rank Fusion paper. It damps the gap
# between first and second place, so one list cannot dominate on a single win.
RRF_K = 60
# How many results each half contributes before fusion.
CANDIDATES_PER_METHOD = 20
# Keyword hits scoring below this fraction of the best hit are discarded rather
# than allowed to vote in the fusion. See keyword_ranking().
KEYWORD_SCORE_FLOOR = 0.35
# If fewer than this fraction of the query's words appear anywhere in the corpus,
# the keyword half abstains entirely. See keyword_ranking().
MIN_QUERY_VOCABULARY_COVERAGE = 0.4
# How many chunks to pull per requested document, so a document can be grounded
# on several of its passages rather than just the one that ranked highest.
CHUNKS_PER_DOCUMENT = 4

logger = logging.getLogger(__name__)


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


@dataclass(frozen=True)
class RetrievalNearMiss:
    title: str
    url: str
    score: float


@dataclass(frozen=True)
class RetrievedUploadDocument:
    source_id: str
    title: str
    organisation: str
    language: str
    page_type: str
    canonical_url: str
    content: str


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
                "visibility": c.visibility,
                "owner_id": c.owner_id,
                "upload_id": c.upload_id,
            }
            for c in chunks
        ],
    }
    path.with_suffix(".json").write_text(json.dumps(metadata), encoding="utf-8")
    if progress:
        print(f"wrote {len(chunks)} vectors to {path} ({path.stat().st_size // 1024} KB)")
    return len(chunks)


def _write_index(chunks: list[KnowledgeChunk], vectors: list[array]) -> None:
    path = vector_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    packed = array("f")
    for vector in vectors:
        packed.extend(vector)
    path.write_bytes(packed.tobytes())
    metadata = {
        "dimensions": len(vectors[0]) if vectors else EXPECTED_DIMENSIONS,
        "count": len(chunks),
        "chunks": [chunk.__dict__ for chunk in chunks],
    }
    path.with_suffix(".json").write_text(json.dumps(metadata), encoding="utf-8")
    load_vector_index.cache_clear()


def index_uploaded_document(
    *, upload_id: str, owner_id: str, filename: str, content: str, visibility: str
) -> int:
    """Embed only the new upload and append it to the existing index."""
    try:
        existing_chunks, existing_vectors = load_vector_index()
    except FileNotFoundError:
        build_vector_index(progress=False)
        existing_chunks, existing_vectors = load_vector_index()
    chunks = chunk_text_document(
        source_id=f"upload:{upload_id}",
        title=filename,
        content=content,
        canonical_url=f"/api/uploads/{upload_id}",
        visibility=visibility,
        owner_id=owner_id if visibility == "private" else None,
        upload_id=upload_id,
    )
    vectors = [array("f", vector) for vector in embed_texts([chunk.embedding_text for chunk in chunks])]
    _write_index([*existing_chunks, *chunks], [*existing_vectors, *vectors])
    return len(chunks)


def set_upload_visibility(upload_id: str, visibility: str, owner_id: str) -> None:
    chunks, vectors = load_vector_index()
    updated = [
        KnowledgeChunk(
            **{
                **chunk.__dict__,
                "visibility": visibility,
                "owner_id": owner_id if visibility == "private" else None,
            }
        )
        if chunk.upload_id == upload_id
        else chunk
        for chunk in chunks
    ]
    _write_index(updated, list(vectors))


def remove_upload_from_index(upload_id: str) -> None:
    chunks, vectors = load_vector_index()
    kept = [(chunk, vector) for chunk, vector in zip(chunks, vectors) if chunk.upload_id != upload_id]
    _write_index([item[0] for item in kept], [item[1] for item in kept])


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


def _keyword_statistics(
    chunks: tuple[KnowledgeChunk, ...], candidate_indices: list[int]
) -> tuple[dict[int, Counter[str]], Counter[str], int]:
    """Build statistics only from chunks the caller is allowed to retrieve."""
    tokenised = {
        index: Counter(_tokens(f"{chunks[index].heading} {chunks[index].section} {chunks[index].text}"))
        for index in candidate_indices
    }
    document_frequency: Counter[str] = Counter()
    for counts in tokenised.values():
        document_frequency.update(counts.keys())
    return tokenised, document_frequency, len(candidate_indices)


def keyword_ranking(
    query: str, chunks: tuple[KnowledgeChunk, ...], candidate_indices: list[int] | None = None
) -> list[int]:
    """Rank chunks by word overlap, weighting each word by how rare it is.

    Without this weighting the scorer treated every matched word alike, so a Dutch
    question about finding information faster was answered with the "Over ons" page:
    it matched "onze", "informatie" and "organisatie", words that appear almost
    everywhere. Rare words carry nearly all the signal, so score by rarity.

    `idf` is the standard BM25 inverse document frequency: a word in almost every
    chunk scores near zero, a word in one chunk scores high. `1 + log(tf)` keeps
    repetition from dominating, matching what knowledge.py already does.
    """
    query_tokens = set(_tokens(query))
    if query_tokens - {"ibc", "group"}:
        query_tokens -= {"ibc", "group"}
    if not query_tokens:
        return []

    candidate_indices = candidate_indices if candidate_indices is not None else list(range(len(chunks)))
    tokenised, document_frequency, total = _keyword_statistics(chunks, candidate_indices)
    idf = {
        token: math.log(
            (total - document_frequency[token] + 0.5) / (document_frequency[token] + 0.5) + 1
        )
        for token in query_tokens
        if document_frequency[token]
    }
    if not idf:
        return []

    # Abstain when the query barely overlaps the corpus vocabulary at all.
    #
    # A German question ("Wie koennen wir unsere Softwarequalitaet verbessern?")
    # had five of its six words absent from this corpus. The survivor was "wie",
    # rare here and therefore scored highly by idf -- but rare in *Dutch*, where it
    # means "who", not the German "how". idf measures rarity, not relevance, so a
    # rare wrong match outranks a common right one, and rank fusion then promotes
    # it. When almost none of the query is in our vocabulary, keyword search has
    # nothing useful to say and meaning should decide alone.
    if len(idf) / len(query_tokens) < MIN_QUERY_VOCABULARY_COVERAGE:
        return []

    scored: list[tuple[float, int]] = []
    for index, counts in tokenised.items():
        length = sum(counts.values())
        if not length:
            continue
        score = sum(
            weight * (1 + math.log(counts[token]))
            for token, weight in idf.items()
            if counts[token]
        )
        if score:
            # Divide by length so a long chunk does not win purely by being long.
            scored.append((score / (length**0.5), index))
    if not scored:
        return []

    scored.sort(key=lambda item: (-item[0], item[1]))
    # A weak list is worse than a short one. Under rank fusion a mediocre entry
    # present in both lists outranks an excellent entry present in one, so keyword
    # results far behind the best are dropped rather than allowed to vote.
    floor = scored[0][0] * KEYWORD_SCORE_FLOOR
    return [index for score, index in scored[:CANDIDATES_PER_METHOD] if score >= floor]


def vector_ranking(
    query: str, vectors: tuple[array, ...], candidate_indices: list[int] | None = None
) -> list[int]:
    """Rank chunks by closeness in meaning."""
    query_vector = embed_query(query)
    query_magnitude = sum(a * a for a in query_vector) ** 0.5
    if not query_magnitude:
        return []
    candidate_indices = candidate_indices if candidate_indices is not None else list(range(len(vectors)))
    scored = [
        (_cosine(query_vector, stored, query_magnitude), index)
        for index in candidate_indices
        for stored in (vectors[index],)
    ]
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [index for _, index in scored[:CANDIDATES_PER_METHOD]]


def hybrid_search(query: str, limit: int = 5, owner_id: str | None = None) -> list[SearchResult]:
    """Filter by access before ranking, then fuse keyword and vector search."""
    chunks, vectors = load_vector_index()
    candidate_indices = [
        index
        for index, chunk in enumerate(chunks)
        if chunk.visibility == "org" or (owner_id is not None and chunk.owner_id == owner_id)
    ]
    keyword = keyword_ranking(query, chunks, candidate_indices)
    semantic = vector_ranking(query, vectors, candidate_indices)

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


def retrieval_mode() -> str:
    """Which retrieval engine the app should use: 'lexical' (default) or 'hybrid'."""
    return os.getenv("SIP_RETRIEVAL", "lexical").strip().lower()


def _relevance_threshold() -> float:
    """Minimum RRF score accepted as evidence.

    0.017 is deliberately just above a single rank-one vote (1/61 = 0.01639),
    requiring agreement between keyword and vector search or multiple meaningful
    votes. Deployments should override this after running the calibration set.
    """
    return float(os.getenv("SIP_RELEVANCE_THRESHOLD", "0.017"))


def retrieve_with_diagnostics(
    query: str, limit: int = 3, owner_id: str | None = None
) -> tuple[list, object, list[RetrievalNearMiss]]:
    """Return documents for grounding, plus the excerpt function to pair with them.

    The seam. `main.py` asks for documents and gets documents, exactly as it did
    when retrieval was a single lexical scorer -- the chat endpoints, the [Source N]
    citations and the prompt construction are untouched. Everything this module
    added lives behind this call.

    Both halves come from one search rather than two, so the query is embedded once.

    Falls back to lexical scoring if the vector index has not been built. That is
    not a nicety: the index is a 13 MB file that does not exist on a fresh deploy,
    and a knowledge assistant that answers slightly worse beats one that returns
    500s until someone runs a build script.
    """
    if retrieval_mode() != "hybrid":
        return search_knowledge(query, limit=limit), create_excerpt, []

    try:
        results = hybrid_search(query, limit=limit * CHUNKS_PER_DOCUMENT, owner_id=owner_id)
    except FileNotFoundError:
        logger.warning(
            "SIP_RETRIEVAL=hybrid but no vector index found at %s; "
            "falling back to lexical retrieval. Build it with build_vector_index().",
            vector_store_path(),
        )
        return search_knowledge(query, limit=limit), create_excerpt, []

    if not results or results[0].score < _relevance_threshold():
        near_misses: list[RetrievalNearMiss] = []
        seen: set[str] = set()
        for result in results:
            if result.chunk.source_id in seen:
                continue
            seen.add(result.chunk.source_id)
            near_misses.append(
                RetrievalNearMiss(
                    title=result.chunk.document_title,
                    url=result.chunk.canonical_url,
                    score=round(result.score, 6),
                )
            )
            if len(near_misses) == limit:
                break
        return [], create_excerpt, near_misses

    # Chunks are the retrieval unit, documents are the citation unit. Keep the order
    # the fusion produced, so the document holding the best chunk is cited first.
    passages: dict[str, list[str]] = {}
    for result in results:
        passages.setdefault(result.chunk.source_id, []).append(result.chunk.text)

    documents = []
    for source_id in list(passages)[:limit]:
        document = get_knowledge_document(source_id)
        if document is not None:
            documents.append(document)
            continue
        chunk = next((item.chunk for item in results if item.chunk.source_id == source_id), None)
        if chunk is not None:
            documents.append(
                RetrievedUploadDocument(
                    source_id=chunk.source_id,
                    title=chunk.document_title,
                    organisation=chunk.organisation,
                    language=chunk.language,
                    page_type=chunk.page_type,
                    canonical_url=chunk.canonical_url,
                    content="\n\n".join(passages[source_id]),
                )
            )

    def excerpt(document, user_query: str, max_characters: int = 2_000) -> str:
        """Ground on the passages retrieval actually matched.

        The lexical excerpt picked paragraphs by shared words with the query, which
        cannot work when the question is in a different language from the document.
        These passages were chosen by meaning, so use them.
        """
        matched = passages.get(document.source_id)
        if not matched:
            return create_excerpt(document, user_query, max_characters)
        return "\n\n".join(matched)[:max_characters].rstrip()

    return documents, excerpt, []


def retrieve(query: str, limit: int = 3) -> tuple[list, object]:
    """Stable retrieval seam used by the rest of the application."""
    documents, excerpt, _ = retrieve_with_diagnostics(query, limit)
    return documents, excerpt
