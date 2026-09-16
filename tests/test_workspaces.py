from pathlib import Path
from uuid import uuid4

from app.models import BusinessContext
from app.store import ContextStore


def fresh_store() -> ContextStore:
    directory = Path(".test-data")
    directory.mkdir(exist_ok=True)
    return ContextStore(directory / f"{uuid4()}.db")


def context(name: str = "Test") -> BusinessContext:
    return BusinessContext(
        name=name,
        offering_type="service",
        short_summary="Summary",
        customer_problems_addressed=[],
        core_capabilities=[],
        target_organisations=[],
        relevant_industries=[],
        relevant_roles_and_decision_makers=[],
        geographic_focus=[],
        value_proposition="",
        differentiators=[],
        people=[],
        supporting_evidence_or_knowledge_sources=[],
        key_marketing_messages=[],
        assumptions=[],
        open_questions=[],
    )


def test_drafts_are_private_and_approved_contexts_are_shared():
    store = fresh_store()
    draft = store.create(context("Private"), "draft", "alice")

    assert store.get(draft.id, "bob") is None
    assert [item.id for item in store.list("bob")] == []
    assert store.get(draft.id, "admin", is_admin=True) is not None

    approved = store.update(draft.id, context("Shared"), "approved", "alice")
    assert approved is not None
    assert store.get(draft.id, "bob") is not None
    assert [item.id for item in store.list("bob")] == [draft.id]


def test_conversations_are_owner_scoped_and_separated_by_kind():
    store = fresh_store()
    context_chat = store.create_conversation("alice", "nl", "context")
    knowledge_chat = store.create_conversation("alice", "nl", "knowledge")
    store.create_conversation("bob", "en", "knowledge")

    assert store.get_conversation(context_chat.id, "bob") is None
    assert [item.id for item in store.list_conversations("alice", kind="knowledge")] == [knowledge_chat.id]
    assert len(store.list_conversations("admin", is_admin=True, kind="knowledge")) == 2


def test_legacy_rows_are_claimed_instead_of_becoming_public():
    store = fresh_store()
    with store._connect() as connection:
        connection.execute(
            "INSERT INTO business_contexts (id, status, content) VALUES ('legacy', 'draft', ?)",
            (context().model_dump_json(),),
        )
    store.backfill_owner("bootstrap")

    assert store.get("legacy", "bootstrap") is not None
    assert store.get("legacy", "someone-else") is None
