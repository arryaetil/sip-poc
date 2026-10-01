"""Product Owner: overviews, refining and updating existing stories (skill routes A, C, E).

Azure DevOps and the model are fakes; these tests prove SIP's rules: who may
read and write, the /rev check, no duplicate or blind writes, real team members only.
"""

import json
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app import devops, main
from app.models import ProductOwnerTurn, StoryDraftContent, WorkItemChange, WorkItemQuery
from app.store import ContextStore

SPRINT = "Etil Solutions\\Sprint 28"
USERS = {
    "arrya@etil.nl": {"password": "a-pass", "role": "product_owner"},
    "viewer@etil.nl": {"password": "v-pass", "role": "product_owner"},
}
MEMBERS = [("Arrya Willems", "arrya@etil.nl"), ("Mark Mennens", "mark@etil.nl"), ("Milan Schils", "milan@etil.nl")]


class FakeAssistant:
    def __init__(self):
        self.turns: list = []
        self.calls: list[dict] = []

    def product_owner_turn(self, history, message, language, owner_id, targets, draft):
        self.calls.append({"history": [m.content for m in history], "targets": targets})
        turn = self.turns.pop(0)
        if isinstance(turn, Exception):
            raise turn
        return turn


class FakeDevOps:
    def __init__(self):
        self.items = {
            1798: {"System.Title": "Rapport exporteren", "System.WorkItemType": "User Story", "System.State": "New",
                   "System.IterationPath": SPRINT, "System.Rev": 4, "Microsoft.VSTS.Scheduling.StoryPoints": 3.0,
                   "System.AssignedTo": {"displayName": "Arrya Willems", "uniqueName": "arrya@etil.nl"},
                   "System.Description": "<p>Export</p>", "Microsoft.VSTS.Common.AcceptanceCriteria": "<ul><li>Werkt</li></ul>",
                   "System.Tags": "AI"},
            1799: {"System.Title": "Inloggen met SSO", "System.WorkItemType": "User Story", "System.State": "Active",
                   "System.IterationPath": SPRINT, "System.Rev": 2,
                   "System.AssignedTo": {"displayName": "Mark Mennens", "uniqueName": "mark@etil.nl"}},
            1700: {"System.Title": "Oude bug", "System.WorkItemType": "Bug", "System.State": "Closed",
                   "System.IterationPath": SPRINT, "System.Rev": 9},
        }
        self.items[1810] = {"System.Title": "Export bouwen", "System.WorkItemType": "Task", "System.State": "New",
                            "System.IterationPath": SPRINT, "System.Rev": 1, "Microsoft.VSTS.Scheduling.RemainingWork": 4.0}
        self.items[1600] = {"System.Title": "Rapportage", "System.WorkItemType": "Feature", "System.State": "Active",
                            "System.IterationPath": "Etil Solutions", "System.Rev": 3}
        self.relations = {1810: [{"rel": "System.LinkTypes.Hierarchy-Reverse", "url": "https://x/_apis/wit/workItems/1798"}],
                          1798: [{"rel": "System.LinkTypes.Hierarchy-Forward", "url": "https://x/_apis/wit/workItems/1810"}]}
        self.comments: dict[int, list[str]] = {}
        self.patch_mode = "ok"
        self.patches: list[list[dict]] = []
        self.posts: list[list[dict]] = []
        self.calls: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.calls.append(f"{request.method} {request.url.path}")
        if url.split("?")[0].endswith("/teams/Etil%20Solutions%20Team/members"):
            return httpx.Response(200, json={"value": [{"identity": {"displayName": d, "uniqueName": u}} for d, u in MEMBERS]})
        if "/workitemtypes/" in url and url.split("?")[0].endswith("/states"):
            work_item_type = request.url.path.split("/workitemtypes/")[1].split("/")[0]
            states = {"User Story": ["New", "Refinement", "To Be Planned", "Ready", "Active", "Resolved", "Closed", "Removed"],
                      "Task": ["New", "Active", "Closed", "Removed"], "Bug": ["New", "Active", "Resolved", "Closed"]}
            return httpx.Response(200, json={"value": [{"name": n} for n in states.get(work_item_type, ["New", "Active", "Resolved", "Closed", "Removed"])]})
        if url.split("?")[0].endswith("/_apis/wit/tags"):
            return httpx.Response(200, json={"value": [{"name": n} for n in ("AI", "Arrya", "Demo")]})
        if "teamsettings/iterations" in url:
            return httpx.Response(200, json={"value": [
                {"name": "Sprint 28", "path": SPRINT, "attributes": {"timeFrame": "current"}},
                {"name": "Sprint 29", "path": "Etil Solutions\\Sprint 29", "attributes": {"timeFrame": "future"}},
            ]})
        if "_apis/wit/wiql" in url:
            query = json.loads(request.content)["query"]
            ids = [i for i, f in self.items.items() if self._matches(query, f)]
            return httpx.Response(200, json={"workItems": [{"id": i} for i in ids]})
        if request.method == "GET" and url.split("?")[0].endswith("/comments"):
            item_id = int(request.url.path.split("/workItems/")[1].split("/")[0])
            return httpx.Response(200, json={"comments": [{"text": t} for t in self.comments.get(item_id, [])]})
        if request.method == "GET" and "_apis/wit/workitems/" in url:
            item_id = int(request.url.path.rsplit("/", 1)[1])
            if item_id not in self.items:
                return httpx.Response(404, json={"message": "not found"})
            return httpx.Response(200, json={"id": item_id, "fields": self.items[item_id], "relations": self.relations.get(item_id, [])})
        if request.method == "GET" and "_apis/wit/workitems" in url:
            ids = [int(i) for i in request.url.params["ids"].split(",")]
            return httpx.Response(200, json={"value": [{"id": i, "fields": self.items[i]} for i in ids]})
        if request.method == "PATCH":
            item_id = int(request.url.path.rsplit("/", 1)[1])
            ops = json.loads(request.content)
            self.patches.append(ops)
            if self.patch_mode == "timeout":
                self._apply(item_id, ops)  # it did happen, but the answer is lost
                raise httpx.ReadTimeout("lost", request=request)
            if ops[0] != {"op": "test", "path": "/rev", "value": self.items[item_id]["System.Rev"]}:
                return httpx.Response(412, json={"message": "TF26071: This work item has been changed by someone else"})
            self._apply(item_id, ops)
            return httpx.Response(200, json={"id": item_id, "rev": self.items[item_id]["System.Rev"], "fields": self.items[item_id]})
        if request.method == "POST" and "workitems/$" in url:
            self.posts.append(json.loads(request.content))
            return httpx.Response(200, json={"id": 1801, "fields": {}, "_links": {"html": {"href": "https://x/1801"}}})
        return httpx.Response(404, json={"message": f"unexpected {url}"})

    def _apply(self, item_id: int, ops: list[dict]) -> None:
        fields = self.items[item_id]
        for op in ops[1:]:
            if op["path"].startswith("/relations/"):
                links = self.relations.setdefault(item_id, [])
                if op["op"] == "remove":
                    links.pop(int(op["path"].rsplit("/", 1)[1]))
                else:
                    links.append(op["value"])
                continue
            if op["path"] == "/fields/System.History":
                self.comments.setdefault(item_id, []).append(op["value"])
                continue
            name = op["path"].removeprefix("/fields/")
            value = op["value"]
            if name == "System.AssignedTo":
                display = next(d for d, u in MEMBERS if u == value)
                value = {"displayName": display, "uniqueName": value}
            fields[name] = value
        fields["System.Rev"] += 1

    @staticmethod
    def _matches(query: str, fields: dict) -> bool:
        if "[System.AssignedTo] = '" in query:
            account = query.split("[System.AssignedTo] = '")[1].split("'")[0]
            if (fields.get("System.AssignedTo") or {}).get("uniqueName") != account:
                return False
            if fields["System.State"] in ("Closed", "Removed"):
                return False
        if "[System.IterationPath] = '" in query:
            path = query.split("[System.IterationPath] = '")[1].split("'")[0]
            if fields["System.IterationPath"] != path:
                return False
        if "IN ('User Story', 'Bug')" in query and fields["System.WorkItemType"] not in ("User Story", "Bug"):
            return False
        if "[System.Title] CONTAINS '" in query:
            if query.split("CONTAINS '")[1].split("'")[0].casefold() not in fields["System.Title"].casefold():
                return False
        if "[System.WorkItemType] = '" in query:
            if fields["System.WorkItemType"] != query.split("[System.WorkItemType] = '")[1].split("'")[0]:
                return False
        if "NOT IN ('Closed', 'Removed')" in query and fields["System.State"] in ("Closed", "Removed"):
            return False
        return True


@pytest.fixture
def env(monkeypatch):
    directory = Path(".test-data")
    directory.mkdir(exist_ok=True)
    store = ContextStore(directory / f"{uuid4()}.db")
    assistant = FakeAssistant()
    fake = FakeDevOps()
    monkeypatch.setenv("SIP_SESSION_SECRET", "test-secret")
    monkeypatch.setenv("SIP_COOKIE_SECURE", "false")
    monkeypatch.setenv("SIP_AUTH_EMAIL", "admin@etil.nl")
    monkeypatch.setenv("SIP_AUTH_PASSWORD", "admin-pass")
    monkeypatch.setenv("SIP_AUTH_EXTRA_USERS", json.dumps(USERS))
    monkeypatch.setenv("SIP_PRODUCT_OWNER_WRITERS", "arrya@etil.nl")
    monkeypatch.setenv("AZURE_DEVOPS_PAT", "test-token")
    monkeypatch.setattr(main, "get_context_store", lambda: store)
    monkeypatch.setattr(main, "get_assistant", lambda: assistant)
    monkeypatch.setattr(devops, "client_factory", lambda settings: httpx.Client(transport=httpx.MockTransport(fake.handler)))
    monkeypatch.setattr(devops, "_STATE_CACHE", {})
    return store, assistant, fake


def signed_in(email: str, password: str) -> TestClient:
    http = TestClient(main.app)
    assert http.post("/api/auth/login", json={"email": email, "password": password}).status_code == 200
    return http


def say(http, assistant, turn, message="vraag", conversation_id=None):
    assistant.turns.append(turn)
    response = http.post("/api/product-owner/chat", json={"message": message, "conversation_id": conversation_id, "language": "nl"})
    assert response.status_code == 200, response.text
    return response.json()


def query_turn(**query) -> ProductOwnerTurn:
    return ProductOwnerTurn(message="Hier is het overzicht.", stage="answer", query=WorkItemQuery(**query))


def change_turn(**change) -> ProductOwnerTurn:
    return ProductOwnerTurn(message="Zo wil ik hem aanpassen.", stage="change_ready", change=WorkItemChange(**change))


def apply(http, change, confirmation_id="confirm-0001", version=None):
    return http.post(
        f"/api/product-owner/changes/{change['id']}/apply",
        json={"version": version or change["version"], "confirmation_id": confirmation_id},
    )


# --- Route A: overviews ---------------------------------------------------------


def test_current_sprint_overview_comes_from_azure_devops(env):
    store, assistant, fake = env
    http = signed_in("arrya@etil.nl", "a-pass")
    body = say(http, assistant, query_turn(kind="sprint"), "Wat staat er in de huidige sprint?")

    result = body["result"]
    assert result["label"] == "Sprint 28" and result["error"] is None
    assert [(item["id"], item["state"]) for item in result["items"]] == [(1798, "New"), (1799, "Active"), (1700, "Closed")]
    assert result["items"][0]["url"].endswith("/_workitems/edit/1798")
    # The model gets display names only, never accounts.
    assert "Mark Mennens" in assistant.calls[0]["targets"] and "mark@etil.nl" not in assistant.calls[0]["targets"]
    assert "Signed-in user in Azure DevOps: Arrya Willems" in assistant.calls[0]["targets"]


def test_assigned_work_for_me_and_for_a_named_colleague(env):
    store, assistant, fake = env
    http = signed_in("arrya@etil.nl", "a-pass")
    mine = say(http, assistant, query_turn(kind="assigned", person="me", iteration_path=SPRINT))["result"]
    assert mine["label"] == "Arrya Willems · Sprint 28" and [i["id"] for i in mine["items"]] == [1798]

    theirs = say(http, assistant, query_turn(kind="assigned", person="mark"), conversation_id=None)["result"]
    assert theirs["label"] == "Mark Mennens · open" and [i["id"] for i in theirs["items"]] == [1799]

    unknown = say(http, assistant, query_turn(kind="assigned", person="Jan"))["result"]
    assert "not a member" in unknown["error"] and unknown["items"] == []


def test_a_story_shows_its_fields_and_the_model_sees_them_next_turn(env):
    store, assistant, fake = env
    http = signed_in("arrya@etil.nl", "a-pass")
    body = say(http, assistant, query_turn(kind="story", work_item_id=1798), "Laat 1798 zien")
    detail = body["result"]["detail"]
    assert detail["rev"] == 4 and detail["acceptance_criteria"] == "- Werkt" and detail["description"] == "Export"

    say(http, assistant, ProductOwnerTurn(message="Wil je hem verfijnen?", stage="answer"), "en nu?", body["conversation_id"])
    notes = [m for m in assistant.calls[1]["history"] if m.startswith("[Azure DevOps via SIP]")]
    assert notes and "Story #1798" in notes[0] and "Werkt" in notes[0]

    timeline = http.get(f"/api/product-owner/conversations/{body['conversation_id']}/timeline").json()
    assert [r["label"] for r in timeline["results"]] == ["User Story #1798"]


def test_accounts_not_on_the_list_cannot_read_through_the_token(env):
    store, assistant, fake = env
    http = signed_in("viewer@etil.nl", "v-pass")
    result = say(http, assistant, query_turn(kind="sprint"))["result"]

    assert "cannot use Azure DevOps" in result["error"] and result["items"] == []
    assert not any("wiql" in call or "members" in call for call in fake.calls)
    assert "not available for this user" in assistant.calls[0]["targets"]
    assert http.get("/api/product-owner/settings").json()["people"] == []


# --- Routes C and E: changes ------------------------------------------------------


def test_status_change_is_shown_confirmed_and_written_with_a_rev_check(env):
    store, assistant, fake = env
    http = signed_in("arrya@etil.nl", "a-pass")
    change = say(http, assistant, change_turn(work_item_id=1798, state="Ready"), "Zet 1798 op Ready")["change"]

    assert change["status"] == "draft" and change["base_rev"] == 4
    assert change["changes"] == [{"field": "state", "before": "New", "after": "Ready"}]
    assert fake.patches == []  # nothing written before the confirmation

    result = apply(http, change).json()
    assert result["status"] == "applied"
    assert fake.patches[0][0] == {"op": "test", "path": "/rev", "value": 4}
    assert fake.patches[0][1:] == [{"op": "add", "path": "/fields/System.State", "value": "Ready"}]
    assert fake.items[1798]["System.State"] == "Ready"

    # The same click again returns the outcome; a new click on an applied change is refused.
    assert apply(http, change).json()["status"] == "applied"
    assert apply(http, change, confirmation_id="confirm-0002").status_code == 409
    assert len(fake.patches) == 1


def test_refinement_assignment_and_sprint_in_one_change(env):
    store, assistant, fake = env
    http = signed_in("arrya@etil.nl", "a-pass")
    change = say(http, assistant, change_turn(
        work_item_id=1798, role="beleidsmedewerker", capability="rapporten exporteren", value="ik tijd bespaar",
        acceptance_criteria=["Export bevat alle wijken", "Opent in Excel"], story_points=5,
        target_kind="sprint", iteration_path="Etil Solutions\\Sprint 29", assigned_to="Mark", language="nl",
    ))["change"]
    fields = [c["field"] for c in change["changes"]]
    assert fields == ["description", "acceptance_criteria", "story_points", "iteration_path", "assigned_to"]
    assert change["changes"][0]["after"].startswith("Als beleidsmedewerker wil ik rapporten exporteren")
    assert change["changes"][-1] == {"field": "assigned_to", "before": "Arrya Willems", "after": "Mark Mennens"}

    apply(http, change)
    ops = {op["path"]: op["value"] for op in fake.patches[0][1:]}
    assert ops["/fields/System.AssignedTo"] == "mark@etil.nl"  # the account, resolved by SIP
    assert ops["/fields/System.IterationPath"] == "Etil Solutions\\Sprint 29"
    assert not any(path.endswith(("System.Tags", "History")) for path in ops)


def test_unsafe_or_empty_changes_are_refused_before_writing(env):
    store, assistant, fake = env
    http = signed_in("arrya@etil.nl", "a-pass")
    cases = [
        (change_turn(work_item_id=1798, assigned_to="Jan"), "not a member"),
        (change_turn(work_item_id=1798, target_kind="sprint", iteration_path="Etil Solutions\\Sprint 1"), "not an open sprint"),
        (change_turn(work_item_id=1798, role="alleen een rol"), "role, capability and value"),
        (change_turn(work_item_id=1798, state="New"), "nothing to change"),
        (change_turn(work_item_id=1700, state="Active"), "does not reopen"),
        (change_turn(work_item_id=4242, state="Active"), "does not exist"),
        # Closed and Removed are refused by SIP itself, whatever the model says.
        (change_turn(work_item_id=1798, state="Closed"), "does not set Closed"),
        (change_turn(work_item_id=1798, state="Removed"), "does not set Removed"),
        (change_turn(work_item_id=1798, state="Done"), "cannot be 'Done'"),
    ]
    for turn, expected in cases:
        body = say(http, assistant, turn)
        assert body["change"] is None and expected in body["result"]["error"], expected
    assert fake.patches == []


def test_a_story_changed_by_someone_else_is_planned_again_not_overwritten(env):
    store, assistant, fake = env
    http = signed_in("arrya@etil.nl", "a-pass")
    change = say(http, assistant, change_turn(work_item_id=1798, state="Ready"))["change"]
    fake.items[1798]["System.Rev"] = 5  # someone edited the story meanwhile

    result = apply(http, change).json()
    assert result["status"] == "failed" and result["version"] == 2 and result["base_rev"] == 5
    assert fake.patches == []  # SIP noticed before writing
    assert apply(http, change, confirmation_id="confirm-0003").status_code == 409  # old version
    assert apply(http, result, confirmation_id="confirm-0004").json()["status"] == "applied"


def test_a_rev_conflict_at_write_time_overwrites_nothing(env, monkeypatch):
    store, assistant, fake = env
    http = signed_in("arrya@etil.nl", "a-pass")
    change = say(http, assistant, change_turn(work_item_id=1798, state="Ready"))["change"]
    real_get = devops.get_item

    def stale_then_real(item_id):
        detail = real_get(item_id)
        fake.items[1798]["System.Rev"] = 6  # changed between SIP's read and its write
        return detail

    monkeypatch.setattr(devops, "get_item", stale_then_real)
    result = apply(http, change).json()
    assert len(fake.patches) == 1 and fake.items[1798]["System.State"] == "New"
    assert result["status"] == "failed" and result["base_rev"] == 6 and "changed this work item" in result["error"]


def test_a_timeout_is_checked_by_reading_the_story(env):
    store, assistant, fake = env
    http = signed_in("arrya@etil.nl", "a-pass")
    change = say(http, assistant, change_turn(work_item_id=1798, state="Ready"))["change"]
    fake.patch_mode = "timeout"

    result = apply(http, change).json()
    assert result["status"] == "uncertain"
    assert apply(http, change, confirmation_id="confirm-0005").status_code == 409  # no blind retry
    checked = http.post(f"/api/product-owner/changes/{change['id']}/check").json()
    assert checked["status"] == "applied" and len(fake.patches) == 1


def test_viewers_cannot_apply_changes(env):
    store, assistant, fake = env
    owner = signed_in("arrya@etil.nl", "a-pass")
    change = say(owner, assistant, change_turn(work_item_id=1798, state="Ready"))["change"]
    viewer = signed_in("viewer@etil.nl", "v-pass")
    assert apply(viewer, change).status_code == 403
    assert fake.patches == []


# --- Route B: assigning a new story ------------------------------------------------


def test_new_story_assignee_is_a_real_team_member(env):
    store, assistant, fake = env
    http = signed_in("arrya@etil.nl", "a-pass")
    content = StoryDraftContent(
        title="Exporteren", role="medewerker", capability="exporteren", value="ik tijd bespaar",
        acceptance_criteria=["Werkt"], story_points=2, target_kind="backlog", assigned_to="milan",
    )
    draft = say(http, assistant, ProductOwnerTurn(message="Voorstel", stage="draft_ready", draft=content))["draft"]
    assert draft["content"]["assigned_to"] == "Milan Schils"
    assert http.get("/api/product-owner/settings").json()["people"] == ["Arrya Willems", "Mark Mennens", "Milan Schils"]

    created = http.post(f"/api/product-owner/drafts/{draft['id']}/create", json={"version": 1, "confirmation_id": "confirm-0006"}).json()
    assert created["status"] == "created"
    fields = {op["path"]: op["value"] for op in fake.posts[0]}
    assert fields["/fields/System.AssignedTo"] == "milan@etil.nl"

    invented = say(http, assistant, ProductOwnerTurn(message="Voorstel", stage="draft_ready",
                                                     draft=content.model_copy(update={"assigned_to": "Piet"})))["draft"]
    assert invented["content"]["assigned_to"] is None


def test_dropped_names_are_reported_and_connecting_words_removed(env):
    store, assistant, fake = env
    http = signed_in("arrya@etil.nl", "a-pass")
    content = StoryDraftContent(
        title="Demo", role="Als demo-gebruiker voor Obvion", capability="wil ik stories opstellen",
        value="zodat zodat ik kan zien hoe het werkt", acceptance_criteria=["Werkt"], story_points=3,
        target_kind="backlog", assigned_to="Piet", tags=["Arrya", "Verzonnen"],
    )
    body = say(http, assistant, ProductOwnerTurn(message="Gedaan.", stage="draft_ready", draft=content))
    draft = body["draft"]
    assert draft["description"] == "Als demo-gebruiker voor Obvion wil ik stories opstellen, zodat ik kan zien hoe het werkt."
    assert draft["content"]["assigned_to"] is None and draft["content"]["tags"] == ["Arrya"]
    assert "SIP heeft dit niet in het voorstel gezet" in body["message"] and "Piet, Verzonnen" in body["message"]


# --- Tags: existing ones only -------------------------------------------------------


def test_existing_tags_can_be_added_and_removed_on_a_story(env):
    store, assistant, fake = env
    http = signed_in("arrya@etil.nl", "a-pass")
    change = say(http, assistant, change_turn(work_item_id=1798, add_tags=["demo"], remove_tags=["AI"]))["change"]
    assert change["changes"] == [{"field": "tags", "before": "AI", "after": "Demo"}]
    assert "Existing tags (only these may be used" in assistant.calls[0]["targets"] and "Demo" in assistant.calls[0]["targets"]

    apply(http, change)
    assert {"op": "add", "path": "/fields/System.Tags", "value": "Demo"} in fake.patches[0]

    refused = say(http, assistant, change_turn(work_item_id=1798, add_tags=["Nieuwe tag"]))
    assert refused["change"] is None and "does not exist" in refused["result"]["error"]
    assert len(fake.patches) == 1


def test_new_story_tags_must_already_exist(env):
    store, assistant, fake = env
    http = signed_in("arrya@etil.nl", "a-pass")
    content = StoryDraftContent(
        title="Exporteren", role="medewerker", capability="exporteren", value="ik tijd bespaar",
        acceptance_criteria=["Werkt"], story_points=2, target_kind="backlog", tags=["ai", "Verzonnen"],
    )
    draft = say(http, assistant, ProductOwnerTurn(message="Voorstel", stage="draft_ready", draft=content))["draft"]
    assert draft["content"]["tags"] == ["AI"]  # real spelling, invented tag dropped
    assert http.get("/api/product-owner/settings").json()["tags"] == ["AI", "Arrya", "Demo"]

    typed = http.put(f"/api/product-owner/drafts/{draft['id']}",
                     json={"version": 1, "content": {**draft["content"], "tags": ["AI", "Bestaat niet"]}}).json()
    response = http.post(f"/api/product-owner/drafts/{draft['id']}/create", json={"version": typed["version"], "confirmation_id": "confirm-0007"})
    assert response.status_code == 422 and "does not exist" in response.json()["detail"]
    assert fake.posts == []

    fixed = http.put(f"/api/product-owner/drafts/{draft['id']}",
                     json={"version": typed["version"], "content": {**draft["content"], "tags": ["AI", "demo"]}}).json()
    http.post(f"/api/product-owner/drafts/{draft['id']}/create", json={"version": fixed["version"], "confirmation_id": "confirm-0008"})
    fields = {op["path"]: op["value"] for op in fake.posts[0]}
    assert fields["/fields/System.Tags"] == "AI; Demo"


# --- All work item types: tasks, bugs, features; comments, parents, search -------------


def test_a_task_is_created_under_a_story_with_remaining_work(env):
    store, assistant, fake = env
    http = signed_in("arrya@etil.nl", "a-pass")
    content = StoryDraftContent(work_item_type="Task", title="Tests schrijven", description="Unit tests voor de export",
                                remaining_work=6, parent_id=1798, target_kind="sprint", iteration_path=SPRINT)
    draft = say(http, assistant, ProductOwnerTurn(message="Taak", stage="draft_ready", draft=content))["draft"]
    assert draft["missing"] == [] and draft["description"] == "Unit tests voor de export"

    created = http.post(f"/api/product-owner/drafts/{draft['id']}/create", json={"version": 1, "confirmation_id": "confirm-0010"}).json()
    assert created["status"] == "created"
    ops = fake.posts[0]
    fields = {op["path"]: op["value"] for op in ops if op["path"].startswith("/fields/")}
    assert fields["/fields/Microsoft.VSTS.Scheduling.RemainingWork"] == 6
    assert "/fields/Microsoft.VSTS.Scheduling.StoryPoints" not in fields
    assert {"op": "add", "path": "/relations/-", "value": {"rel": "System.LinkTypes.Hierarchy-Reverse",
            "url": "https://dev.azure.com/EtilSolutions/_apis/wit/workItems/1798"}} in ops
    assert any("$Task" in call for call in fake.calls)


def test_a_bug_description_goes_to_repro_steps_and_types_have_their_own_rules(env):
    store, assistant, fake = env
    http = signed_in("arrya@etil.nl", "a-pass")
    bug = StoryDraftContent(work_item_type="Bug", title="Export faalt", description="Klik op export\nFoutmelding 500",
                            priority=1, target_kind="backlog")
    draft = say(http, assistant, ProductOwnerTurn(message="Bug", stage="draft_ready", draft=bug))["draft"]
    assert draft["missing"] == []
    http.post(f"/api/product-owner/drafts/{draft['id']}/create", json={"version": 1, "confirmation_id": "confirm-0011"})
    fields = {op["path"]: op["value"] for op in fake.posts[0]}
    assert fields["/fields/Microsoft.VSTS.TCM.ReproSteps"] == "<p>Klik op export</p><p>Foutmelding 500</p>"
    assert fields["/fields/Microsoft.VSTS.Common.Priority"] == 1

    epic = StoryDraftContent(work_item_type="Epic", title="Platform", description="Groot thema", target_kind="backlog")
    epic_draft = say(http, assistant, ProductOwnerTurn(message="Epic", stage="draft_ready", draft=epic), conversation_id=None)["draft"]
    assert epic_draft["missing"] == ["priority"]

    refused = say(http, assistant, change_turn(work_item_id=1810, story_points=3))
    assert "no story points" in refused["result"]["error"]
    refused = say(http, assistant, change_turn(work_item_id=1810, state="Ready"))
    assert "cannot be 'Ready'" in refused["result"]["error"] and "New, Active" in refused["result"]["error"]


def test_a_comment_and_a_new_parent_are_written_with_the_rev_check(env):
    store, assistant, fake = env
    http = signed_in("arrya@etil.nl", "a-pass")
    change = say(http, assistant, change_turn(work_item_id=1810, parent_id=1600, remaining_work=2,
                                             comment="Export is bijna klaar"))["change"]
    assert change["work_item_type"] == "Task"
    assert [c["field"] for c in change["changes"]] == ["remaining_work", "parent", "comment"]
    assert change["changes"][1] == {"field": "parent", "before": "#1798", "after": "#1600 Rapportage"}

    assert apply(http, change).json()["status"] == "applied"
    ops = fake.patches[0]
    assert ops[0] == {"op": "test", "path": "/rev", "value": 1}
    assert {"op": "remove", "path": "/relations/0"} in ops  # one parent: the old link goes
    assert fake.relations[1810][-1]["url"].endswith("/workItems/1600")
    assert fake.comments[1810] == ["<p>Export is bijna klaar</p>"]


def test_an_uncertain_comment_is_found_by_reading_the_comments(env):
    store, assistant, fake = env
    http = signed_in("arrya@etil.nl", "a-pass")
    change = say(http, assistant, change_turn(work_item_id=1798, comment="Graag review"))["change"]
    fake.patch_mode = "timeout"
    assert apply(http, change).json()["status"] == "uncertain"
    assert http.post(f"/api/product-owner/changes/{change['id']}/check").json()["status"] == "applied"


def test_search_and_children(env):
    store, assistant, fake = env
    http = signed_in("arrya@etil.nl", "a-pass")
    found = say(http, assistant, query_turn(kind="search", text="export"))["result"]
    assert sorted(i["id"] for i in found["items"]) == [1798, 1810] and found["label"] == '"export"'

    tasks = say(http, assistant, query_turn(kind="search", work_item_type="Task"))["result"]
    assert [i["id"] for i in tasks["items"]] == [1810]

    children = say(http, assistant, query_turn(kind="children", work_item_id=1798))["result"]
    assert children["label"] == "#1798 · children" and [i["id"] for i in children["items"]] == [1810]

    detail = say(http, assistant, query_turn(kind="story", work_item_id=1810))["result"]
    assert detail["label"] == "Task #1810" and detail["detail"]["parent_id"] == 1798 and detail["detail"]["remaining_work"] == 4.0
