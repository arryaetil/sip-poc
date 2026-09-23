"""One-off, idempotent: prepare the Dify knowledge base for per-user uploads.

Dify has no per-user permissions inside a knowledge base. SIP therefore labels
every document with an `owner` metadata value: `public` for the reviewed ETIL
corpus, a pseudonymous user label for a private upload. The knowledge app only
retrieves documents whose owner is `public` or the asking user.

This script creates the `owner` field if it is missing and marks every document
that is not a SIP upload as `public`.

    DIFY_DATASET_API_KEY=dataset-... python dify/setup_knowledge_metadata.py
"""

from __future__ import annotations

import os
import sys

import httpx

BASE = os.getenv("DIFY_API_BASE", "https://api.dify.ai/v1").rstrip("/")
DATASET_ID = os.getenv("DIFY_DATASET_ID", "cc833d3d-e595-41c7-a7ca-1bc1c5b7decd")
UPLOAD_PREFIX = "upload:"


def main() -> None:
    key = os.getenv("DIFY_DATASET_API_KEY", "").strip()
    if not key:
        sys.exit("Set DIFY_DATASET_API_KEY (Knowledge → Service API key, starts with dataset-).")
    http = httpx.Client(base_url=BASE, headers={"Authorization": f"Bearer {key}"}, timeout=60)

    fields = http.get(f"/datasets/{DATASET_ID}/metadata").raise_for_status().json()["doc_metadata"]
    owner = next((field for field in fields if field["name"] == "owner"), None)
    if owner is None:
        owner = http.post(f"/datasets/{DATASET_ID}/metadata", json={"type": "string", "name": "owner"}).raise_for_status().json()
        print(f"created metadata field owner ({owner['id']})")
    else:
        print(f"metadata field owner exists ({owner['id']})")

    documents = http.get(f"/datasets/{DATASET_ID}/documents", params={"page": 1, "limit": 100}).raise_for_status().json()["data"]
    corpus = [document for document in documents if not document["name"].startswith(UPLOAD_PREFIX)]
    http.post(
        f"/datasets/{DATASET_ID}/documents/metadata",
        json={
            "operation_data": [
                {
                    "document_id": document["id"],
                    "metadata_list": [{"id": owner["id"], "name": "owner", "value": "public"}],
                }
                for document in corpus
            ]
        },
    ).raise_for_status()
    print(f"marked {len(corpus)} corpus documents as public")
    print(f"owner field id: {owner['id']}")


if __name__ == "__main__":
    main()
