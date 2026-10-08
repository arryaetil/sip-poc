"""Business Context versions: every save is a version with who, when and how;
history, field changes, restore, and updating an approved context through a
conversation. The model is a fake."""

import json
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import main
from app.models import BusinessContext, ProductStrategistTurn
from app.store import ContextStore

USERS = {
    "po@test.nl": {"password": "po-pass", "role": "product_owner"},
    "po2@test.nl": {"password": "po2-pass", "role": "product_owner"},
    "sales@test.nl": {"password": "sales-pass", "role": "sales"},
}


def context(name: str = "WoonAtlas", targets: list[str] | None = None) -> BusinessContext:
    return BusinessContext(
        name=name, offering_type="product", short_summary="Dashboard", customer_problems_addressed=[],
        core_capabilities=[], target_organisations=targets or ["Gemeenten"], relevant_industries=[],
        relevant_roles_and_decision_makers=[], geographic_focus=[], value_proposition="Inzicht",
        differentiators=[], people=[], supporting_evidence_or_knowledge_sources=[], key_marketing_messages=[],
        assumptions=[], open_questions=[],
    )


class FakeAssistant:
    def __init__(self):
        self.strategist_calls: list[dict] = []
        self.prepared: list = []
        self.next_context = context(targets=["Gemeenten", "Woningcorporaties"])

    def strategist_turn(self, history, message, language, owner_id, extra_instructions=""):
        self.strategist_calls.append({"history": history, "extra": extra_instructions})
        return ProductStrategistTurn(message="Wat is er veranderd?", is_ready_to_save=True, readiness_reason="Duidelijk")

    def prepare_context(self, history, owner_id):
        self.prepared.append(history)
        return self.next_context

    def index_context(self, context, owner_id):
        pass

    def remove_context(self, context_id):
        pass


@pytest.fixture
def env(monkeypatch):
    directory = Path(".test-data")
    directory.mkdir(exist_ok=True)
    store = ContextStore(directory / f"{uuid4()}.db")
    assistant = FakeAssistant()
    monkeypatch.setenv("SIP_SESSION_SECRET", "test-secret")
    monkeypatch.setenv("SIP_COOKIE_SECURE", "false")
    monkeypatch.setenv("SIP_AUTH_EMAIL", "admin@test.nl")
    monkeypatch.setenv("SIP_AUTH_PASSWORD", "admin-pass")
    monkeypatch.setenv("SIP_AUTH_EXTRA_USERS", json.dumps(USERS))
    monkeypatch.setattr(main, "get_context_store", lambda: store)
    monkeypatch.setattr(main, "get_assistant", lambda: assistant)
    return store, assistant


def signed_in(email: str, password: str) -> TestClient:
    http = TestClient(main.app)
    assert http.post("/api/auth/login", json={"email": email, "password": password}).status_code == 200
    return http


def approved(store: ContextStore, owner: str = "someone") -> str:
    return store.create(context(), "approved", owner, changed_by="maker@test.nl").id


def save(http: TestClient, context_id: str, body: BusinessContext, source: str = "form"):
    return http.put(f"/api/contexts/{context_id}", json={"context": body.model_dump(), "status": "approved", "source": source})


def test_every_change_is_a_version_with_who_and_how(env):
    store, _ = env
    context_id = approved(store)
    po = signed_in("po@test.nl", "po-pass")
    assert save(po, context_id, context()).status_code == 200  # nothing changed: no new version
    assert save(po, context_id, context(targets=["Gemeenten", "Provincies"])).status_code == 200
    history = po.get(f"/api/contexts/{context_id}/versions").json()
    assert [item["version"] for item in history] == [2, 1]
    assert history[0]["changed_by"] == "po@test.nl" and history[0]["source"] == "form"
    assert history[0]["changed_fields"] == ["target_organisations"]
    assert history[1]["changed_by"] == "maker@test.nl" and history[1]["source"] == "created"
    detail = po.get(f"/api/contexts/{context_id}/versions/2").json()
    assert detail["changes"] == [{"field": "target_organisations", "kind": "list", "before": "", "after": "",
                                  "removed": [], "added": ["Provincies"]}]


def test_product_owners_change_any_approved_context_sales_only_reads(env):
    store, _ = env
    context_id = approved(store, owner="po@test.nl")
    draft = store.create(context("Concept"), "draft", "someone-else").id
    other_po = signed_in("po2@test.nl", "po2-pass")
    assert save(other_po, context_id, context(targets=["Provincies"])).status_code == 200
    assert save(other_po, draft, context("Concept")).status_code == 404  # drafts stay their owner's
    sales = signed_in("sales@test.nl", "sales-pass")
    assert sales.get(f"/api/contexts/{context_id}/versions").status_code == 200
    assert save(sales, context_id, context()).status_code == 403
    assert sales.post(f"/api/contexts/{context_id}/versions/1/restore").status_code == 403


def test_restore_is_a_new_version_and_loses_nothing(env):
    store, _ = env
    context_id = approved(store)
    po = signed_in("po@test.nl", "po-pass")
    save(po, context_id, context(targets=["Provincies"]))
    restored = po.post(f"/api/contexts/{context_id}/versions/1/restore")
    assert restored.status_code == 200 and restored.json()["target_organisations"] == ["Gemeenten"]
    history = po.get(f"/api/contexts/{context_id}/versions").json()
    assert [(item["version"], item["source"], item["restored_from"]) for item in history] == [
        (3, "restore", 1), (2, "form", None), (1, "created", None)
    ]
    assert restored.json()["status"] == "approved"


def test_update_through_a_conversation(env):
    store, assistant = env
    context_id = approved(store)
    sales = signed_in("sales@test.nl", "sales-pass")
    assert sales.post("/api/conversations", json={"updates_context_id": context_id}).status_code == 403
    po = signed_in("po@test.nl", "po-pass")
    draft = store.create(context("Concept"), "draft", "someone").id
    assert po.post("/api/conversations", json={"updates_context_id": draft}).status_code == 404
    conversation = po.post("/api/conversations", json={"updates_context_id": context_id, "language": "nl"}).json()
    assert conversation["updates_context_id"] == context_id
    po.post(f"/api/conversations/{conversation['id']}/messages", json={"message": "Ook voor woningcorporaties"})
    call = assistant.strategist_calls[-1]
    assert call["history"][0].content.startswith("[SIP] Current version") and '"Gemeenten"' in call["history"][0].content
    assert "updates an existing" in call["extra"] and len(call["extra"]) < 4000  # Dify's limit
    # Saving as a new context is refused; the proposal shows what would change.
    assert po.post(f"/api/conversations/{conversation['id']}/portfolio").status_code == 409
    proposal = po.post(f"/api/conversations/{conversation['id']}/update-proposal").json()
    assert proposal["context_id"] == context_id
    assert proposal["changes"][0]["added"] == ["Woningcorporaties"]
    assert len(po.get(f"/api/contexts/{context_id}/versions").json()) == 1  # nothing saved yet
    assert save(po, context_id, BusinessContext(**proposal["proposal"]), source="conversation").status_code == 200
    assert po.get(f"/api/contexts/{context_id}/versions").json()[0]["source"] == "conversation"


def test_contexts_from_before_versions_start_at_one_and_versions_go_with_the_context(env):
    store, _ = env
    with sqlite3.connect(store.database_path) as connection:
        connection.execute(
            "INSERT INTO business_contexts (id, status, content, owner_id) VALUES ('old', 'approved', ?, 'x')",
            (context().model_dump_json(),),
        )
    store = ContextStore(store.database_path)  # startup runs the backfill
    assert [row["source"] for row in store.list_context_versions("old")] == ["existing"]
    assert store.delete_context("old", "x")
    assert store.list_context_versions("old") == []
