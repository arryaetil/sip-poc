"""What changed between two versions of a Business Context, field by field.

Every save of a Business Context stores a full copy (store.business_context_versions),
with who saved it, when and how (created, conversation, form, restore). This module
only compares two copies; it decides nothing about who may save.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.models import BusinessContext

SOURCES = ("existing", "created", "conversation", "form", "restore")


class FieldChange(BaseModel):
    field: str
    kind: Literal["text", "list"]
    before: str = ""
    after: str = ""
    removed: list[str] = []
    added: list[str] = []


class ContextVersionSummary(BaseModel):
    version: int
    status: Literal["draft", "approved"]
    changed_by: str | None
    source: Literal["existing", "created", "conversation", "form", "restore"]
    restored_from: int | None
    created_at: str
    changed_fields: list[str]


class ContextVersionDetail(ContextVersionSummary):
    context: BusinessContext
    changes: list[FieldChange]


class ContextUpdateProposal(BaseModel):
    """What a conversation would change, before anything is saved."""

    context_id: str
    current: BusinessContext
    proposal: BusinessContext
    changes: list[FieldChange]


def diff(before: dict | None, after: dict) -> list[FieldChange]:
    """Changed fields in BusinessContext order. With no previous version, nothing changed."""
    if before is None:
        return []
    changes: list[FieldChange] = []
    for name in BusinessContext.model_fields:
        old, new = before.get(name), after.get(name)
        if isinstance(new, list) or isinstance(old, list):
            old_items, new_items = [str(item) for item in old or []], [str(item) for item in new or []]
            removed = [item for item in old_items if item not in new_items]
            added = [item for item in new_items if item not in old_items]
            if removed or added:
                changes.append(FieldChange(field=name, kind="list", removed=removed, added=added))
        elif (old or "") != (new or ""):
            changes.append(FieldChange(field=name, kind="text", before=str(old or ""), after=str(new or "")))
    return changes
