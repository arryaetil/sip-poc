"""Push every existing Business Context and upload to the active assistant's index.

Saving a context or uploading a file already keeps the index current; this is
for data that existed before, or after a knowledge base is recreated. Safe to
run twice: documents are updated in place, not duplicated.

    python -m app.reindex          (inside the container: railway ssh)
"""

from __future__ import annotations

from pathlib import Path
import logging

from app.assistants import get_assistant
from app.main import get_context_store

logging.basicConfig(level=logging.INFO)


def main() -> None:
    assistant = get_assistant()
    store = get_context_store()
    print(f"provider: {assistant.name}")

    with store._connect() as connection:
        contexts = connection.execute("SELECT id, owner_id FROM business_contexts").fetchall()
        uploads = connection.execute(
            "SELECT id, owner_id, filename, storage_path, visibility FROM uploads"
        ).fetchall()

    for row in contexts:
        context = store.get(row["id"], row["owner_id"], is_admin=True)
        if context is None:
            continue
        assistant.index_context(context, row["owner_id"])
        print(f"context  {context.status:8} {context.name}")

    for row in uploads:
        text_path = Path(f"{row['storage_path']}.txt")
        if not text_path.exists():
            print(f"upload   skipped (no extracted text) {row['filename']}")
            continue
        assistant.index_upload(
            upload_id=row["id"],
            owner_id=row["owner_id"],
            filename=row["filename"],
            content=text_path.read_text(encoding="utf-8"),
            visibility=row["visibility"],
        )
        print(f"upload   {row['visibility']:8} {row['filename']}")

    print(f"done: {len(contexts)} contexts, {len(uploads)} uploads")


if __name__ == "__main__":
    main()
