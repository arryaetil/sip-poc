"""Business Context versions: the history, one version with what changed, restore,
and the proposal an update conversation makes before anything is saved.

Reading the history is open to everyone who can read the context (sales included).
Restoring and saving go through the same rule as editing: Product Owner and admin
(POST is not allowed for sales in `_role_allows`, and `update` checks it again).
"""

from __future__ import annotations

import json
import logging
import traceback

from fastapi import APIRouter, HTTPException, Request

from app.context_versions import (
    ContextUpdateProposal,
    ContextVersionDetail,
    ContextVersionSummary,
    diff,
)
from app.models import BusinessContext, StoredBusinessContext

logger = logging.getLogger("sip")
router = APIRouter(prefix="/api")


def _main():
    from app import main

    return main


def _readable_context(context_id: str, request: Request) -> StoredBusinessContext:
    main = _main()
    owner_id, is_admin = main._actor(request)
    context = main.get_context_store().get(context_id, owner_id, is_admin)
    if context is None:
        raise HTTPException(status_code=404, detail="Business Context not found")
    return context


def _versions(context_id: str) -> list[dict]:
    """Oldest first, each with its content parsed and the fields that changed."""
    rows = [dict(row) for row in reversed(_main().get_context_store().list_context_versions(context_id))]
    previous = None
    for row in rows:
        row["content"] = json.loads(row["content"])
        row["changes"] = diff(previous["content"] if previous else None, row["content"])
        fields = [change.field for change in row["changes"]]
        if previous and previous["status"] != row["status"]:
            fields.insert(0, "status")
        row["changed_fields"] = fields
        previous = row
    return rows


def _summary(row: dict) -> ContextVersionSummary:
    return ContextVersionSummary(
        version=row["version"], status=row["status"], changed_by=row["changed_by"], source=row["source"],
        restored_from=row["restored_from"], created_at=row["created_at"], changed_fields=row["changed_fields"],
    )


@router.get("/contexts/{context_id}/versions", response_model=list[ContextVersionSummary])
def list_versions(context_id: str, request: Request) -> list[ContextVersionSummary]:
    _readable_context(context_id, request)
    return [_summary(row) for row in reversed(_versions(context_id))]


@router.get("/contexts/{context_id}/versions/{version}", response_model=ContextVersionDetail)
def get_version(context_id: str, version: int, request: Request) -> ContextVersionDetail:
    _readable_context(context_id, request)
    row = next((item for item in _versions(context_id) if item["version"] == version), None)
    if row is None:
        raise HTTPException(status_code=404, detail="Version not found")
    return ContextVersionDetail(**_summary(row).model_dump(), context=BusinessContext(**row["content"]), changes=row["changes"])


@router.post("/contexts/{context_id}/versions/{version}/restore", response_model=StoredBusinessContext)
def restore_version(context_id: str, version: int, request: Request) -> StoredBusinessContext:
    """Put an old version's content back. That is a new version; nothing is removed."""
    main = _main()
    current = _readable_context(context_id, request)
    row = next((item for item in _versions(context_id) if item["version"] == version), None)
    if row is None:
        raise HTTPException(status_code=404, detail="Version not found")
    owner_id, is_admin = main._actor(request)
    restored = main.get_context_store().update(
        context_id, BusinessContext(**row["content"]), current.status, owner_id, is_admin,
        may_edit_approved=main._may_edit_approved(request),
        changed_by=main._changed_by(request),
        source="restore",
        restored_from=version,
    )
    if restored is None:
        raise HTTPException(status_code=403, detail="Your role cannot change this Business Context")
    main._sync_context_knowledge(restored)
    return restored


@router.post("/conversations/{conversation_id}/update-proposal", response_model=ContextUpdateProposal)
def update_proposal(conversation_id: str, request: Request) -> ContextUpdateProposal:
    """The context as the conversation would leave it, next to the current one. Not saved:
    the user reviews it and saves through PUT /api/contexts/{id} with source "conversation"."""
    main = _main()
    store = main.get_context_store()
    owner_id, is_admin = main._actor(request)
    conversation = store.get_conversation(conversation_id, owner_id, is_admin)
    if conversation is None or not conversation.updates_context_id:
        raise HTTPException(status_code=404, detail="Update conversation not found")
    if not conversation.is_ready_to_save:
        raise HTTPException(status_code=409, detail="The changes need more information before they can be reviewed.")
    current = store.get(conversation.updates_context_id, owner_id, is_admin)
    if current is None:
        raise HTTPException(status_code=404, detail="The Business Context being updated no longer exists")
    history = main._update_history(conversation, owner_id, is_admin)
    try:
        proposal = main.get_assistant().prepare_context(history, owner_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Update proposal failed:\n%s", traceback.format_exc())
        raise HTTPException(status_code=502, detail="Preparing the changes failed; please try again.") from exc
    before = BusinessContext(**current.model_dump())
    return ContextUpdateProposal(
        context_id=current.id, current_status=current.status, current=before, proposal=proposal, changes=diff(before.model_dump(), proposal.model_dump())
    )
