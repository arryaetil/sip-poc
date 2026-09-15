"""Turn text into vectors using the Azure AI Foundry embedding deployment.

This module is deliberately thin. It is one HTTP call behind a plain Python
signature, which is the whole reason the C# port stays small: a model running
inside the process would have to be rewritten, a web request does not.

Endpoint note, learned the hard way: chat answers on the *project* endpoint
(.../api/projects/<project>) while the embedding deployment answers on the
*resource root*. Same resource, same key, different path -- asking the project
path for embeddings returns a bare 404 that looks exactly like a missing
deployment. The root is therefore derived from the configured endpoint.
"""

from __future__ import annotations

from functools import lru_cache
import os
from urllib.parse import urlsplit

from openai import OpenAI

DEFAULT_DEPLOYMENT = "text-embedding-3-large"
# text-embedding-3-large returns 3072 numbers per passage. This number is baked
# into any vector index built from it: changing the model means re-embedding the
# whole corpus AND rebuilding the index. See MIGRATION.md.
EXPECTED_DIMENSIONS = 3072
# Requests carry many passages at once. Kept modest so one oversized batch cannot
# breach the deployment's tokens-per-minute allowance.
BATCH_SIZE = 64


def embedding_deployment() -> str:
    return os.getenv("EMBEDDING_DEPLOYMENT", "").strip() or DEFAULT_DEPLOYMENT


def _embedding_base_url() -> str:
    """The resource root, derived from the project endpoint unless overridden."""
    override = os.getenv("AZURE_AI_EMBEDDING_ENDPOINT", "").strip()
    endpoint = override or os.getenv("AZURE_AI_PROJECT_ENDPOINT", "").strip()
    if not endpoint:
        raise RuntimeError("AZURE_AI_PROJECT_ENDPOINT is not configured")
    parts = urlsplit(endpoint)
    return f"{parts.scheme}://{parts.netloc}/openai/v1/"


@lru_cache(maxsize=1)
def get_embedding_client() -> OpenAI:
    """Authenticate the same way the rest of the app does.

    A key is required. It is read from the environment and never written to disk
    or logged. Production should prefer the managed-identity path below, so no
    secret exists to leak or rotate.
    """
    api_key = os.getenv("AZURE_AI_API_KEY", "").strip()
    if not api_key:
        # Mirrors get_openai_client() in main.py: without a key, fall back to the
        # Azure identity of whatever is running the process.
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider

        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
        )
        return OpenAI(base_url=_embedding_base_url(), api_key=token_provider())

    return OpenAI(
        base_url=_embedding_base_url(),
        api_key=api_key,
        default_headers={"api-key": api_key},
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed many passages, in batches, preserving input order."""
    if not texts:
        return []

    client = get_embedding_client()
    deployment = embedding_deployment()
    vectors: list[list[float]] = []
    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start : start + BATCH_SIZE]
        response = client.embeddings.create(model=deployment, input=batch)
        # The API may return items out of order; index is authoritative.
        vectors.extend(item.embedding for item in sorted(response.data, key=lambda i: i.index))
    return vectors


def embed_query(text: str) -> list[float]:
    """Embed a single search query."""
    return embed_texts([text])[0]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """How close two vectors point in the same direction: 1.0 identical, 0.0 unrelated.

    Written out rather than pulled from numpy so the POC adds no dependency. At
    1,104 chunks this is fast enough; a larger corpus wants numpy or a real index.
    """
    dot = sum(a * b for a, b in zip(left, right))
    left_magnitude = sum(a * a for a in left) ** 0.5
    right_magnitude = sum(b * b for b in right) ** 0.5
    if not left_magnitude or not right_magnitude:
        return 0.0
    return dot / (left_magnitude * right_magnitude)
