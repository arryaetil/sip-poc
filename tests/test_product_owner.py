"""Product Owner: drafting, versions, permissions and the Azure DevOps write.

Azure DevOps and the model are fakes here. These tests prove SIP's behaviour
(no write without approval, no duplicate, no blind retry), not a real connection.
"""

import json
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app import assistants, devops, main
from app.models import ProductOwnerTurn, StoryDraftContent
from app.store import ContextStore

USERS = {
    "po@test.nl": {"password": "po-pass", "role": "product_owner"},
    "other@test.nl": {"password": "other-pass", "role": "product_owner"},
    "sales@test.nl": {"password": "sales-pass", "role": "sales"},
}
SPRINT = "Etil Solutions\\Sprint 28"

COMPLETE = StoryDraftContent(
    title="Exporteer de woningvoorraad naar Excel",
    role="beleidsmedewerker",
    capability="de woningvoorraad per wijk exporteren naar Excel",
    value="ik zonder handwerk rapportages kan maken",
    entry_criteria=["Toegang tot de testdata"],
    acceptance_criteria=["De export bevat alle wijken", "Het bestand opent in Excel <script>"],
    story_points=3,
    estimation_reason="Bestaande exportfunctie kan worden hergebruikt.",
    target_kind="sprint",
    iteration_path=SPRINT,
)


class FakeAssistant:
    def __init__(self):
        self.turns: list = []
        self.calls: list[dict] = []

    def product_owner_turn(self, history, message, language, owner_id, targets, draft):
        self.calls.append({"message": message, "targets": targets, "draft": draft, "history": len(history)})
        turn = self.turns.pop(0)
        if isinstance(turn, Exception):
            raise turn
        return turn


class FakeDevOps:
    """Answers like Azure DevOps; `create` decides what a story POST does."""

    def __init__(self):
        self.create = "ok"
        self.found: list[int] = []
        self.posts: list[list[dict]] = []
        self.wiql: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        assert request.headers["Authorization"].startswith("Basic ")
        if "teamsettings/iterations" in url:
            return httpx.Response(200, json={"value": [
                {"name": "Sprint 27", "path": "Etil Solutions\\Sprint 27", "attributes": {"timeFrame": "past"}},
                {"name": "Sprint 28", "path": SPRINT, "attributes": {
                    "timeFrame": "current", "startDate": "2026-09-22T00:00:00Z", "finishDate": "2026-10-12T00:00:00Z"}},
                {"name": "Sprint 29", "path": "Etil Solutions\\Sprint 29", "attributes": {"timeFrame": "future"}},
            ]})
        if "workitems/$User" in url and request.method == "POST":
            self.posts.append(json.loads(request.content))
            if self.create == "timeout":
                raise httpx.ReadTimeout("no answer", request=request)
            if self.create == "reject":
                return httpx.Response(400, json={"message": "TF401320: Rule error for field Story Points."})
            if self.create == "auth":
                return httpx.Response(401, text="")
            fields = {item["path"].removeprefix("/fields/"): item["value"] for item in self.posts[-1]}
            return httpx.Response(200, json={
                "id": 4242,
                "fields": fields,
                "_links": {"html": {"href": "https://dev.azure.com/EtilSolutions/Etil%20Solutions/_workitems/edit/4242"}},
            })
        if "_apis/wit/wiql" in url:
            self.wiql.append(json.loads(request.content)["query"])
            return httpx.Response(200, json={"workItems": [{"id": item} for item in self.found]})
        if "_apis/wit/workitems" in url and request.method == "GET":
            return httpx.Response(200, json={"value": [
                {"id": item, "fields": {"System.Title": COMPLETE.title, "System.IterationPath": SPRINT}} for item in self.found
            ]})
        return httpx.Response(404, json={"message": "unexpected"})


@pytest.fixture
def po(monkeypatch):
    directory = Path(".test-data")
    directory.mkdir(exist_ok=True)
    store = ContextStore(directory / f"{uuid4()}.db")
    assistant = FakeAssistant()
    fake_devops = FakeDevOps()
    monkeypatch.setenv("SIP_SESSION_SECRET", "test-secret")
    monkeypatch.setenv("SIP_COOKIE_SECURE", "false")
    monkeypatch.setenv("SIP_AUTH_EMAIL", "admin@test.nl")
    monkeypatch.setenv("SIP_AUTH_PASSWORD", "admin-pass")
    monkeypatch.setenv("SIP_AUTH_EXTRA_USERS", json.dumps(USERS))
    monkeypatch.setenv("SIP_PRODUCT_OWNER_WRITERS", "po@test.nl")
    monkeypatch.setenv("AZURE_DEVOPS_PAT", "test-token")
    monkeypatch.setattr(main, "get_context_store", lambda: store)
    monkeypatch.setattr(main, "get_assistant", lambda: assistant)
    monkeypatch.setattr(
        devops, "client_factory",
        lambda settings: httpx.Client(transport=httpx.MockTransport(fake_devops.handler), headers={"Authorization": "Basic x"}),
    )
    return store, assistant, fake_devops


def signed_in(email: str, password: str) -> TestClient:
    http = TestClient(main.app)
    assert http.post("/api/auth/login", json={"email": email, "password": password}).status_code == 200
    return http


def draft_turn(content: StoryDraftContent = COMPLETE, message: str = "Hier is het voorstel.") -> ProductOwnerTurn:
    return ProductOwnerTurn(message=message, stage="draft_ready", draft=content)


def start_with_draft(http: TestClient, assistant: FakeAssistant, content: StoryDraftContent = COMPLETE) -> dict:
    assistant.turns.append(draft_turn(content))
    response = http.post("/api/product-owner/chat", json={"message": "Excel-export", "language": "nl"})
    assert response.status_code == 200, response.text
    return response.json()


def create(http: TestClient, draft: dict, confirmation_id: str = "confirm-0001", version: int | None = None):
    return http.post(
        f"/api/product-owner/drafts/{draft['id']}/create",
        json={"version": version or draft["version"], "confirmation_id": confirmation_id},
    )


# --- Asking, drafting, resuming ------------------------------------------------


def test_a_question_without_draft_stores_the_turn_but_no_proposal(po):
    store, assistant, fake = po
    http = signed_in("po@test.nl", "po-pass")
    assistant.turns.append(ProductOwnerTurn(
        message="Voor wie is dit bedoeld?", stage="clarifying", open_questions=["Voor wie?", "En waarom?"]
    ))
    body = http.post("/api/product-owner/chat", json={"message": "Een export", "language": "nl"}).json()

    assert body["draft"] is None
    assert body["open_questions"] == ["Voor wie?"]  # never more than one question
    conversation = http.get(f"/api/conversations/{body['conversation_id']}").json()
    assert conversation["kind"] == "product_owner"
    assert [m["role"] for m in conversation["messages"]] == ["user", "assistant"]
    # The model only sees sprints SIP fetched; past sprints are not offered.
    assert SPRINT in assistant.calls[0]["targets"] and "Sprint 27" not in assistant.calls[0]["targets"]
    assert fake.posts == []


def test_proposal_is_saved_versioned_and_comes_back_after_reload(po):
    store, assistant, fake = po
    http = signed_in("po@test.nl", "po-pass")
    body = start_with_draft(http, assistant)
    draft = body["draft"]

    assert draft["version"] == 1 and draft["status"] == "draft" and draft["missing"] == []
    assert draft["description"] == (
        "Als beleidsmedewerker wil ik de woningvoorraad per wijk exporteren naar Excel, "
        "zodat ik zonder handwerk rapportages kan maken."
    )
    reloaded = http.get(f"/api/product-owner/conversations/{body['conversation_id']}/drafts").json()
    assert [item["id"] for item in reloaded] == [draft["id"]]

    # The next turn sees the saved draft and an updated proposal becomes version 2.
    assistant.turns.append(draft_turn(COMPLETE.model_copy(update={"story_points": 5})))
    second = http.post(
        "/api/product-owner/chat",
        json={"message": "Maak het 5 punten", "conversation_id": body["conversation_id"], "language": "nl"},
    ).json()
    assert COMPLETE.title in assistant.calls[1]["draft"]
    assert second["draft"]["id"] == draft["id"] and second["draft"]["version"] == 2
    assert fake.posts == []  # drafting never writes to Azure DevOps


def test_a_sprint_the_server_did_not_offer_is_dropped_from_the_model_draft(po):
    store, assistant, fake = po
    http = signed_in("po@test.nl", "po-pass")
    invented = COMPLETE.model_copy(update={"iteration_path": "Etil Solutions\\Sprint 99"})
    draft = start_with_draft(http, assistant, invented)["draft"]

    assert draft["content"]["iteration_path"] is None
    assert "target" in draft["missing"]


def test_invalid_model_output_is_a_clear_error_and_keeps_the_draft(po):
    store, assistant, fake = po
    http = signed_in("po@test.nl", "po-pass")
    body = start_with_draft(http, assistant)
    assistant.turns.append(ValueError("The model did not return a valid ProductOwnerTurn"))

    response = http.post(
        "/api/product-owner/chat",
        json={"message": "Pas het aan", "conversation_id": body["conversation_id"], "language": "nl"},
    )
    assert response.status_code == 502
    assert "unchanged" in response.json()["detail"]
    drafts = http.get(f"/api/product-owner/conversations/{body['conversation_id']}/drafts").json()
    assert drafts[0]["version"] == 1


def test_dify_outage_is_reported_as_unavailable(po):
    store, assistant, fake = po
    http = signed_in("po@test.nl", "po-pass")
    assistant.turns.append(assistants.AssistantUnavailable("Dify is busy"))
    response = http.post("/api/product-owner/chat", json={"message": "Idee", "language": "nl"})
    assert response.status_code == 503


# --- Permissions ---------------------------------------------------------------


def test_sales_has_no_access_and_others_cannot_read_or_confirm(po):
    store, assistant, fake = po
    owner = signed_in("po@test.nl", "po-pass")
    body = start_with_draft(owner, assistant)
    draft = body["draft"]

    sales = signed_in("sales@test.nl", "sales-pass")
    assert sales.post("/api/product-owner/chat", json={"message": "x"}).status_code == 403
    assert sales.get("/api/product-owner/settings").status_code == 403

    other = signed_in("other@test.nl", "other-pass")
    assert other.get(f"/api/product-owner/conversations/{body['conversation_id']}/drafts").status_code == 404
    assert other.put(f"/api/product-owner/drafts/{draft['id']}", json={"version": 1, "content": COMPLETE.model_dump()}).status_code == 404
    assert other.post("/api/product-owner/chat", json={"message": "x", "conversation_id": body["conversation_id"]}).status_code == 404

    # Admins can read, as with every conversation, but cannot act for the owner.
    admin = signed_in("admin@test.nl", "admin-pass")
    assert admin.get(f"/api/product-owner/conversations/{body['conversation_id']}/drafts").status_code == 200
    assert create(admin, draft).status_code == 403  # not on the writer list
    assert fake.posts == []


def test_only_listed_writers_can_create(po, monkeypatch):
    store, assistant, fake = po
    http = signed_in("po@test.nl", "po-pass")
    draft = start_with_draft(http, assistant)["draft"]
    monkeypatch.setenv("SIP_PRODUCT_OWNER_WRITERS", "")

    assert http.get("/api/product-owner/settings").json()["can_create"] is False
    assert create(http, draft).status_code == 403
    assert fake.posts == []


def test_a_writer_cannot_confirm_someone_elses_proposal(po, monkeypatch):
    store, assistant, fake = po
    owner = signed_in("other@test.nl", "other-pass")
    draft = start_with_draft(owner, assistant)["draft"]
    writer = signed_in("po@test.nl", "po-pass")

    assert create(writer, draft).status_code == 404
    assert fake.posts == []


# --- Approval, versions and the write ------------------------------------------


def test_confirmed_version_is_created_once_with_the_agreed_fields(po):
    store, assistant, fake = po
    http = signed_in("po@test.nl", "po-pass")
    draft = start_with_draft(http, assistant)["draft"]

    result = create(http, draft)
    assert result.status_code == 200
    record = result.json()
    assert record["status"] == "created" and record["devops_id"] == 4242
    assert record["devops_url"].endswith("/_workitems/edit/4242")

    fields = {item["path"]: item["value"] for item in fake.posts[0]}
    assert fields["/fields/System.Title"] == COMPLETE.title
    assert fields["/fields/System.IterationPath"] == SPRINT
    assert fields["/fields/Microsoft.VSTS.Scheduling.StoryPoints"] == 3
    assert "&lt;script&gt;" in fields["/fields/Microsoft.VSTS.Common.AcceptanceCriteria"]
    assert "Als beleidsmedewerker wil ik" in fields["/fields/System.Description"]
    # No tags, states, assignees: only what the user approved.
    assert not any(path.endswith(("System.Tags", "System.State", "System.AssignedTo")) for path in fields)

    # The same click arriving twice returns the stored result without a second write.
    again = create(http, draft)
    assert again.status_code == 200 and again.json()["devops_id"] == 4242
    assert create(http, draft, confirmation_id="confirm-0002").status_code == 409
    assert len(fake.posts) == 1


def test_backlog_uses_the_project_root(po):
    store, assistant, fake = po
    http = signed_in("po@test.nl", "po-pass")
    draft = start_with_draft(http, assistant, COMPLETE.model_copy(update={"target_kind": "backlog", "iteration_path": None}))["draft"]
    assert create(http, draft).json()["status"] == "created"
    fields = {item["path"]: item["value"] for item in fake.posts[0]}
    assert fields["/fields/System.IterationPath"] == "Etil Solutions"


def test_an_edit_makes_the_earlier_confirmation_stale(po):
    store, assistant, fake = po
    http = signed_in("po@test.nl", "po-pass")
    draft = start_with_draft(http, assistant)["draft"]
    edited = http.put(
        f"/api/product-owner/drafts/{draft['id']}",
        json={"version": 1, "content": {**COMPLETE.model_dump(), "title": "Andere titel"}},
    )
    assert edited.status_code == 200 and edited.json()["version"] == 2

    assert create(http, draft, version=1).status_code == 409
    # An edit based on an old version is refused too, instead of overwriting.
    assert http.put(f"/api/product-owner/drafts/{draft['id']}", json={"version": 1, "content": COMPLETE.model_dump()}).status_code == 409
    assert fake.posts == []
    assert create(http, edited.json(), confirmation_id="confirm-0003").json()["content"]["title"] == "Andere titel"


def test_incomplete_proposal_or_closed_sprint_is_refused_before_writing(po):
    store, assistant, fake = po
    http = signed_in("po@test.nl", "po-pass")
    draft = start_with_draft(http, assistant, COMPLETE.model_copy(update={"acceptance_criteria": []}))["draft"]
    assert create(http, draft).status_code == 422

    closed = http.put(
        f"/api/product-owner/drafts/{draft['id']}",
        json={"version": 1, "content": {**COMPLETE.model_dump(), "iteration_path": "Etil Solutions\\Sprint 27"}},
    ).json()
    response = create(http, closed, confirmation_id="confirm-0004")
    assert response.status_code == 422 and "sprint" in response.json()["detail"]
    assert fake.posts == []


def test_refusal_or_expired_token_keeps_the_draft_open(po):
    store, assistant, fake = po
    http = signed_in("po@test.nl", "po-pass")
    draft = start_with_draft(http, assistant)["draft"]

    fake.create = "reject"
    record = create(http, draft).json()
    assert record["status"] == "failed" and "TF401320" in record["error"]
    assert record["devops_id"] is None

    fake.create = "auth"
    record = create(http, record, confirmation_id="confirm-0005").json()
    assert record["status"] == "failed" and "token" in record["error"]

    fake.create = "ok"
    record = create(http, record, confirmation_id="confirm-0006").json()
    assert record["status"] == "created"
    assert len(fake.posts) == 3


def test_a_timeout_is_uncertain_and_is_checked_instead_of_retried(po):
    store, assistant, fake = po
    http = signed_in("po@test.nl", "po-pass")
    draft = start_with_draft(http, assistant)["draft"]

    fake.create = "timeout"
    record = create(http, draft).json()
    assert record["status"] == "uncertain" and record["devops_id"] is None
    fake.create = "ok"
    assert create(http, draft, confirmation_id="confirm-0007").status_code == 409
    assert http.put(f"/api/product-owner/drafts/{draft['id']}", json={"version": 1, "content": COMPLETE.model_dump()}).status_code == 409
    assert len(fake.posts) == 1  # no blind retry

    fake.found = [4243]
    checked = http.post(f"/api/product-owner/drafts/{draft['id']}/check").json()
    assert checked["status"] == "created" and checked["devops_id"] == 4243
    assert "@me" in fake.wiql[0] and COMPLETE.title in fake.wiql[0]
    assert len(fake.posts) == 1


def test_an_uncertain_write_that_did_not_happen_can_be_confirmed_again(po):
    store, assistant, fake = po
    http = signed_in("po@test.nl", "po-pass")
    draft = start_with_draft(http, assistant)["draft"]
    fake.create = "timeout"
    create(http, draft)

    fake.found = []
    checked = http.post(f"/api/product-owner/drafts/{draft['id']}/check").json()
    assert checked["status"] == "failed"
    fake.create = "ok"
    assert create(http, checked, confirmation_id="confirm-0008").json()["status"] == "created"


def test_a_write_cut_off_halfway_becomes_uncertain(po):
    store, assistant, fake = po
    http = signed_in("po@test.nl", "po-pass")
    body = start_with_draft(http, assistant)
    draft = body["draft"]
    owner_id = store.get_story_draft(draft["id"], "", is_admin=True)["owner_id"]
    assert store.begin_story_create(draft["id"], owner_id, 1, "confirm-0009", "po@test.nl", COMPLETE)
    with store._connect() as connection:
        connection.execute("UPDATE story_drafts SET updated_at = datetime('now', '-10 minutes') WHERE id = ?", (draft["id"],))

    drafts = http.get(f"/api/product-owner/conversations/{body['conversation_id']}/drafts").json()
    assert drafts[0]["status"] == "uncertain"
    assert fake.posts == []


def test_after_creation_a_new_proposal_starts_a_new_draft(po):
    store, assistant, fake = po
    http = signed_in("po@test.nl", "po-pass")
    body = start_with_draft(http, assistant)
    create(http, body["draft"])
    assistant.turns.append(draft_turn(COMPLETE.model_copy(update={"title": "Deel twee"})))
    second = http.post(
        "/api/product-owner/chat",
        json={"message": "Nu deel twee", "conversation_id": body["conversation_id"], "language": "nl"},
    ).json()

    assert second["draft"]["id"] != body["draft"]["id"] and second["draft"]["version"] == 1
    drafts = http.get(f"/api/product-owner/conversations/{body['conversation_id']}/drafts").json()
    assert [item["status"] for item in drafts] == ["created", "draft"]


def test_two_claims_on_the_same_version_only_one_wins():
    directory = Path(".test-data")
    directory.mkdir(exist_ok=True)
    store = ContextStore(directory / f"{uuid4()}.db")
    conversation = store.create_conversation("alice", "nl", "product_owner")
    draft = store.save_model_story_draft(conversation.id, "alice", "nl", COMPLETE)

    assert store.begin_story_create(draft["id"], "alice", 1, "click-one-1", "alice", COMPLETE)
    assert not store.begin_story_create(draft["id"], "alice", 1, "click-two-2", "alice", COMPLETE)
    assert store.save_model_story_draft(conversation.id, "alice", "nl", COMPLETE) is None


# --- Separation from the rest of SIP --------------------------------------------


def test_product_owner_conversations_stay_out_of_other_features(po):
    store, assistant, fake = po
    http = signed_in("po@test.nl", "po-pass")
    body = start_with_draft(http, assistant)
    conversation_id = body["conversation_id"]

    assert [c["id"] for c in http.get("/api/conversations?kind=product_owner").json()] == [conversation_id]
    assert http.get("/api/conversations?kind=knowledge").json() == []
    assert http.get("/api/conversations?kind=context").json() == []
    assert http.post(f"/api/conversations/{conversation_id}/messages", json={"message": "x"}).status_code == 404
    assert http.post("/api/knowledge/chat", json={"message": "x", "conversation_id": conversation_id}).status_code == 404


def test_missing_devops_configuration_still_allows_drafting(po, monkeypatch):
    store, assistant, fake = po
    monkeypatch.delenv("AZURE_DEVOPS_PAT")
    http = signed_in("po@test.nl", "po-pass")
    settings = http.get("/api/product-owner/settings").json()
    assert settings["devops_configured"] is False and settings["can_create"] is False

    draft = start_with_draft(http, assistant, COMPLETE.model_copy(update={"iteration_path": None}))["draft"]
    assert "No targets" in assistant.calls[0]["targets"]
    assert create(http, draft).status_code == 422  # no sprint chosen; nothing sent anywhere


def test_dify_starts_without_the_product_owner_key(monkeypatch):
    for name, value in {
        "DIFY_STRATEGIST_API_KEY": "app-strategist",
        "DIFY_FINALIZER_API_KEY": "app-finalizer",
        "DIFY_KNOWLEDGE_API_KEY": "app-knowledge",
        "DIFY_DATASET_API_KEY": "dataset-kb",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("DIFY_PRODUCT_OWNER_API_KEY", raising=False)
    assistant = assistants.DifyAssistant()  # the other assistants keep working

    with pytest.raises(assistants.AssistantUnavailable):
        assistant.product_owner_turn([], "idee", "nl", "alice", "", "")


def test_dify_product_owner_receives_targets_and_draft(monkeypatch):
    for name in ("DIFY_STRATEGIST_API_KEY", "DIFY_FINALIZER_API_KEY", "DIFY_KNOWLEDGE_API_KEY", "DIFY_DATASET_API_KEY"):
        monkeypatch.setenv(name, "app-x")
    monkeypatch.setenv("DIFY_PRODUCT_OWNER_API_KEY", "app-po")
    sent = []
    answer = ProductOwnerTurn(message="Voor wie?", stage="clarifying").model_dump_json()

    def handler(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"answer": answer})

    assistant = assistants.DifyAssistant()
    assistant.http = httpx.Client(transport=httpx.MockTransport(handler))
    turn = assistant.product_owner_turn([], "idee", "nl", "alice", "- backlog", '{"title": "x"}')

    assert turn.message == "Voor wie?"
    assert sent[0]["inputs"]["targets"] == "- backlog" and sent[0]["inputs"]["draft"] == '{"title": "x"}'
    assert sent[0]["user"] != "alice"  # Dify sees a pseudonym, never SIP's user id
    assert "test-token" not in json.dumps(sent[0])


def test_home_offers_the_product_owner_to_the_right_roles(monkeypatch):
    monkeypatch.delenv("SIP_SESSION_SECRET", raising=False)
    http = TestClient(main.app)
    page = http.get("/").text
    assert 'data-specialist="product-owner"' in page
    assert 'data-view="product-owner" data-roles="admin product_owner"' in page
    assert 'data-video="/avatars/product-owner.mp4"' not in page  # still image until a video exists
    assert http.get("/avatars/product-owner.webp").status_code == 200
    assert http.get("/avatars/product-owner.png").headers["content-type"] == "image/png"
    # The living robot: the eyeless base image plus eye positions on the 1254 px grid.
    assert 'data-base="/avatars/product-owner-base.webp"' in page and 'data-eyes="551,298,64;730,353,64"' in page
    assert http.get("/avatars/product-owner-base.webp").status_code == 200
    # Product Owner is the fourth card, so it starts the second row of three.
    order = [page.index(f'data-specialist="{name}"') for name in ("marketing", "knowledge", "kyc", "product-owner")]
    assert order == sorted(order)
