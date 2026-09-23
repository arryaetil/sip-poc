"""Put the reviewed ETIL corpus into the Dify knowledge base, one chunk per section.

Dify splits on blank lines and ignores a custom separator when a document is
updated, so a markdown page became dozens of fragments: a heading such as
"Robotic Process Automation (RPA)" in one chunk, its text in another, and bare
"Rol van Etil" headings on every solution page matching any question about ETIL.

This script prepares the text itself. Each `##` section becomes one paragraph,
prefixed with the page title, with no blank lines inside; Dify then produces one
chunk per section and only splits sections that are too long. Documents keep
their file name (SIP maps it back to title and URL) and the `owner = public`
label. Safe to run again: existing documents are updated in place.

    DIFY_DATASET_API_KEY=dataset-... python dify/sync_corpus.py
"""

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "knowledge" / "markdown" / "etil"
BASE = os.getenv("DIFY_API_BASE", "https://api.dify.ai/v1").rstrip("/")
DATASET_ID = os.getenv("DIFY_DATASET_ID", "cc833d3d-e595-41c7-a7ca-1bc1c5b7decd")
PACE = 7  # seconds between requests; the Sandbox plan allows ~10 per minute


def sections(path: Path) -> str:
    """The page as one paragraph per `##` section, each prefixed with the page title."""
    raw = path.read_text(encoding="utf-8")
    front, _, body = raw.partition("\n---\n") if raw.startswith("---") else ("", "", raw)
    title_match = re.search(r'^title:\s*"?(.*?)"?\s*$', front, re.MULTILINE)
    title = (title_match.group(1) if title_match else path.stem).replace(" - Etil", "").strip()

    blocks: list[tuple[str, list[str]]] = [("", [])]
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("## ") or stripped.startswith("# "):
            blocks.append((stripped.lstrip("# ").strip(), []))
        else:
            blocks[-1][1].append(stripped.lstrip("# ").strip())

    paragraphs = []
    for heading, lines in blocks:
        if not lines and not heading:
            continue
        label = f"{title} — {heading}" if heading else title
        paragraphs.append(label + ":\n" + "\n".join(lines) if lines else label)
    return "\n\n".join(paragraphs)


def main() -> None:
    key = os.getenv("DIFY_DATASET_API_KEY", "").strip()
    if not key:
        sys.exit("Set DIFY_DATASET_API_KEY (Knowledge → Service API key, starts with dataset-).")
    http = httpx.Client(base_url=f"{BASE}/datasets/{DATASET_ID}", headers={"Authorization": f"Bearer {key}"}, timeout=120)

    def call(method: str, path: str, **kwargs) -> dict:
        for _ in range(4):
            time.sleep(PACE)
            response = http.request(method, path, **kwargs)
            if response.status_code in (403, 429) and "rate limit" in response.text:
                print("  rate limit, waiting 65 s")
                time.sleep(65)
                continue
            response.raise_for_status()
            return response.json() if response.content else {}
        raise RuntimeError("rate limit")

    owner = next(field for field in call("GET", "/metadata")["doc_metadata"] if field["name"] == "owner")
    existing = {d["name"]: d["id"] for d in call("GET", "/documents", params={"page": 1, "limit": 100})["data"]}

    ids = []
    for index, path in enumerate(sorted(CORPUS.glob("*.md")), start=1):
        body = {"name": path.name, "text": sections(path), "indexing_technique": "high_quality",
                "doc_form": "text_model", "doc_language": "Dutch", "process_rule": {"mode": "automatic"}}
        if path.name in existing:
            call("POST", f"/documents/{existing[path.name]}/update-by-text", json=body)
            ids.append(existing[path.name])
        else:
            ids.append(call("POST", "/document/create-by-text", json=body)["document"]["id"])
        print(f"[{index:2}] {path.name}")

    call("POST", "/documents/metadata", json={"operation_data": [
        {"document_id": item, "metadata_list": [{"id": owner["id"], "name": "owner", "value": "public"}]} for item in ids
    ]})
    print(f"done: {len(ids)} documents, all owner=public")


if __name__ == "__main__":
    main()
