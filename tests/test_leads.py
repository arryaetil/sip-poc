"""Lead finder: the brief, the score, the contact rules, the search and the routes.

Serper, the websites and the model are fakes. These tests prove what SIP enforces
whatever the model answers: at most 50 leads, a source for every fact, organisation
data and generic contact details only, roles, and deletion after the retention period.
"""

import json
from pathlib import Path
import socket
from uuid import uuid4

import httpx
from openpyxl import load_workbook
from io import BytesIO
import pytest
from fastapi.testclient import TestClient

from app import assistants, lead_routes, main
from app.assistants import AssistantUnavailable, DifyAssistant
from app.lead_search import LeadSearch, PageFetcher, SearchResult, page_text
from app.leads import (
    LeadBrief,
    LeadCandidate,
    LeadCandidates,
    LeadColumn,
    LeadExtraction,
    LeadExtraValue,
    LeadFact,
    LeadIntakeTurn,
    LeadQuery,
    LeadQueryPlan,
    LeadRow,
    ScoreCriterion,
    build_row,
    clean_brief,
    company_phone,
    export_xlsx,
    generic_email,
    linkedin_people_page,
    score_row,
)
from app.models import BusinessContext
from app.store import ContextStore

USERS = {
    "sales@test.nl": {"password": "sales-pass", "role": "sales"},
    "po@test.nl": {"password": "po-pass", "role": "product_owner"},
}
BRANCHES = LeadColumn(name="Vestigingen", description="aantal vestigingen")
SCORECARD = [
    ScoreCriterion(column="Vestigingen", kind="number", high="10", medium="4"),
    ScoreCriterion(column="country", kind="text", high="Nederland, Belgi", medium="Duitsland"),
]


def brief(count: int | None = 3, **changes) -> LeadBrief:
    values = dict(
        title="Autodealergroepen Limburg",
        description="Dealergroepen met meerdere vestigingen",
        industries=["automotive"],
        regions=["NL-Limburg"],
        size="Minimaal 4 vestigingen",
        exclude=["Eenmanszaken"],
        extra_columns=[BRANCHES],
        scorecard=SCORECARD,
        count=count,
    )
    return LeadBrief(**{**values, **changes})


def row(branches: str | None, country: str | None = "Nederland") -> LeadRow:
    return LeadRow(
        name="Mengelers",
        website="https://mengelers.nl/",
        country=LeadFact(value=country, source="https://mengelers.nl/") if country else LeadFact(),
        extra={"Vestigingen": LeadFact(value=branches, source="https://mengelers.nl/") if branches else LeadFact()},
    )


# --------------------------------------------------------------------------- brief and score


def test_brief_is_clamped_to_fifty_and_three_columns():
    columns = [LeadColumn(name=f"Kolom {i}", description="x") for i in range(5)]
    cleaned = clean_brief(brief(count=500, extra_columns=columns, scorecard=[
        ScoreCriterion(column="kolom 1", kind="number", high="1", medium="0"),
        ScoreCriterion(column="Unknown column", kind="number", high="1", medium="0"),
        ScoreCriterion(column="Country", kind="text", high="NL", medium=""),
    ]))
    assert cleaned.count == 50
    assert [c.name for c in cleaned.extra_columns] == ["Kolom 0", "Kolom 1", "Kolom 2"]
    assert [c.column for c in cleaned.scorecard] == ["Kolom 1", "country"]
    assert clean_brief(brief(count=0)).count == 1
    assert clean_brief(brief(count=None)).count is None


def test_score_comes_from_the_scorecard_and_unknown_is_never_high():
    assert score_row(row("27 vestigingen"), SCORECARD).level == "high"
    assert score_row(row("6", country="Duitsland"), SCORECARD).level == "medium"
    assert score_row(row("6"), SCORECARD).level == "medium"  # one high, one medium: not mostly high
    assert score_row(row("2", country="Frankrijk"), SCORECARD).level == "low"
    unknown = score_row(row(None), SCORECARD)
    assert unknown.level == "medium"  # country high, branches unknown: capped below high
    assert [c.level for c in unknown.criteria] == ["unknown", "high"]
    assert score_row(row("1.200"), SCORECARD).criteria[0].level == "high"
    assert score_row(row("27"), []).level is None


# --------------------------------------------------------------------------- contact rules


@pytest.mark.parametrize("value, kept", [
    ("info@mengelers.nl", True),
    ("mailto:hr@anmgroup.be", True),
    ("service-audi-bonn@fleischhauer.com", True),
    ("aarschot@pashuysen.be", True),
    ("jan.peeters@dealer.be", False),
    ("j.peeters@dealer.be", False),
    ("info.limburg@dealer.nl", True),
    ("not an email", False),
])
def test_only_generic_email_addresses_are_kept(value, kept):
    assert (generic_email(value) is not None) is kept


@pytest.mark.parametrize("value, country, kept", [
    ("046 452 1000", "Nederland", True),
    ("+31 6 12345678", None, False),
    ("06-12345678", "Nederland", False),
    ("+32 475 12 34 56", None, False),
    ("0475 12 34 56", "BE", False),
    ("04 222 33 44", "BE", True),
    ("+49 171 1234567", None, False),
    ("123", None, False),
])
def test_mobile_numbers_are_not_kept(value, country, kept):
    assert (company_phone(value, country) is not None) is kept


def test_linkedin_is_only_a_company_people_page():
    assert linkedin_people_page("https://nl.linkedin.com/company/mengelers-groep") == (
        "https://www.linkedin.com/company/mengelers-groep/people/"
    )
    assert linkedin_people_page("https://www.linkedin.com/in/jan-peeters") is None


# --------------------------------------------------------------------------- grounding


def test_a_fact_without_a_fetched_source_or_not_on_its_page_is_dropped():
    pages = {
        "https://mengelers.nl/": "Mengelers, Sittard. Bel 046 452 1000 of mail info@mengelers.nl",
        "https://mengelers.nl/vestigingen": "Onze 9 vestigingen in Limburg",
    }
    extraction = LeadExtraction(
        fits=True,
        name="Mengelers Automotive",
        city=LeadFact(value="Sittard", source="https://mengelers.nl/"),
        country=LeadFact(value="Nederland", source="https://elsewhere.example/"),  # not fetched
        phone=LeadFact(value="046 999 9999", source="https://mengelers.nl/"),  # not on the page
        email=LeadFact(value="info@mengelers.nl", source="https://mengelers.nl/"),
        extra=[LeadExtraValue(column="vestigingen", value="9", source="https://mengelers.nl/vestigingen")],
        why_fits="Dealergroep met 9 vestigingen.",
    )
    built = build_row(LeadCandidate(name="Mengelers", website="https://mengelers.nl"), pages, extraction, [BRANCHES])
    assert built.city.value == "Sittard"
    assert built.country.value is None
    assert built.phone.value is None
    assert built.email.value == "info@mengelers.nl"
    assert built.extra["Vestigingen"] == LeadFact(value="9", source="https://mengelers.nl/vestigingen")
    assert built.sources == ["https://mengelers.nl/", "https://mengelers.nl/vestigingen"]


# --------------------------------------------------------------------------- page fetching


def test_pages_on_private_addresses_are_never_fetched():
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(200, text="<a href='/contact'>x</a>", headers={"content-type": "text/html"})

    def resolver(host, port):
        address = "10.0.0.5" if host == "intranet.example" else "93.184.216.34"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 0))]

    fetcher = PageFetcher(http=httpx.Client(transport=httpx.MockTransport(handler)), resolver=resolver)
    assert fetcher.fetch("http://intranet.example/") is None
    assert fetcher.fetch("http://127.0.0.1/") is None
    assert fetcher.fetch("https://www.linkedin.com/company/x/") is None
    assert not any("intranet" in url or "127.0.0.1" in url or "linkedin" in url for url in requests)


def test_redirects_to_private_addresses_are_refused_and_robots_txt_is_respected():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private")
        if request.url.path == "/jump":
            return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data"})
        return httpx.Response(200, text="<p>ok</p>", headers={"content-type": "text/html"})

    def resolver(host, port):
        address = host if host[0].isdigit() else "93.184.216.34"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 0))]

    fetcher = PageFetcher(http=httpx.Client(transport=httpx.MockTransport(handler)), resolver=resolver)
    assert fetcher.fetch("https://dealer.example/jump") is None
    assert fetcher.fetch("https://dealer.example/private/page") is None
    assert fetcher.fetch("https://dealer.example/about")[1] == "ok"


def test_compressed_pages_are_read():
    import gzip

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        body = gzip.compress("<p>Welkom bij de dealer</p>".encode())
        return httpx.Response(200, content=body, headers={"content-type": "text/html; charset=utf-8", "content-encoding": "gzip"})

    def resolver(host, port):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

    fetcher = PageFetcher(http=httpx.Client(transport=httpx.MockTransport(handler)), resolver=resolver)
    assert fetcher.site_pages("https://dealer.example") == {"https://dealer.example": "Welkom bij de dealer"}


def test_page_text_keeps_contact_links_and_drops_scripts():
    text = page_text("<script>var x=1</script><p>Welkom</p><a href='mailto:info@x.nl'>mail</a><a href='tel:0464521000'>bel</a>")
    assert "var x" not in text
    assert "Welkom" in text
    assert "mailto:info@x.nl" in text and "tel:0464521000" in text


# --------------------------------------------------------------------------- the search


class FakeSerper:
    def __init__(self):
        self.queries: list[str] = []

    def search(self, query, country="nl", num=10):
        self.queries.append(query)
        if "site:linkedin.com" in query:
            return [SearchResult("x", "https://www.linkedin.com/in/someone", ""),
                    SearchResult("x", "https://nl.linkedin.com/company/dealer-groep", query)]
        return [SearchResult(f"Dealer {i}", f"https://dealer{i}.example/", "dealer") for i in range(6)] + [
            SearchResult("Gids", "https://www.goudengids.nl/dealers", "")
        ]


class FakeFetcher:
    def site_pages(self, website):
        return {website.rstrip("/") + "/": "Dealergroep. Bel 046 452 1000, info@dealer.example. 12 vestigingen"}


class FakeLeadAssistant:
    def __init__(self):
        self.extracted: list[str] = []
        self.intake: list[LeadIntakeTurn] = []

    def lead_available(self):
        return True

    def lead_intake_turn(self, history, message, language, owner_id, context_text, brief_json):
        return self.intake.pop(0)

    def lead_queries(self, brief_json, previous_json, language, owner_id):
        return LeadQueryPlan(queries=[LeadQuery(query="autodealergroep limburg", country="nl")])

    def lead_select(self, brief_json, results, needed, owner_id):
        assert "goudengids" not in results
        return LeadCandidates(candidates=[
            LeadCandidate(name=f"Dealer {i}", website=f"https://dealer{i}.example") for i in range(6)
        ])

    def lead_extract(self, brief_json, company_json, pages, language, owner_id):
        website = json.loads(company_json)["website"].rstrip("/") + "/"
        self.extracted.append(website)
        return LeadExtraction(
            fits=True,
            name=json.loads(company_json)["name"],
            city=LeadFact(value="Sittard", source=website),
            country=LeadFact(value="Nederland", source=website),
            phone=LeadFact(value="046 452 1000", source=website),
            email=LeadFact(value="info@dealer.example", source=website),
            extra=[LeadExtraValue(column="Vestigingen", value="12", source=website)],
            why_fits="Groep met 12 vestigingen.",
        )


@pytest.fixture
def store():
    directory = Path(".test-data")
    directory.mkdir(exist_ok=True)
    return ContextStore(directory / f"{uuid4()}.db")


def approved_context(store: ContextStore, owner: str = "admin") -> str:
    context = BusinessContext(
        name="SAM", offering_type="service", short_summary="Software asset management",
        customer_problems_addressed=[], core_capabilities=[], target_organisations=["Dealergroepen"],
        relevant_industries=["automotive"], relevant_roles_and_decision_makers=[], geographic_focus=["Limburg"],
        value_proposition="", differentiators=[], people=[], supporting_evidence_or_knowledge_sources=[],
        key_marketing_messages=[], assumptions=[], open_questions=[],
    )
    return store.create(context, "approved", owner).id


def test_search_stops_at_the_requested_count_and_keeps_sources(store):
    list_id = store.create_lead_list("owner", None, "ctx", "SAM", clean_brief(brief(count=3)), "nl")
    assistant = FakeLeadAssistant()
    LeadSearch(store, assistant, FakeSerper(), FakeFetcher()).run(list_id, "owner", "nl", "context")
    record = store.get_lead_list(list_id)
    assert record.status == "done"
    assert len(record.rows) == 3
    first = record.rows[0]
    assert first.phone.value == "046 452 1000" and first.phone.source == first.website
    assert first.linkedin == "https://www.linkedin.com/company/dealer-groep/people/"
    assert score_row(first, record.brief.scorecard).level == "high"


def test_a_failing_search_settles_the_list(store):
    list_id = store.create_lead_list("owner", None, "ctx", "SAM", clean_brief(brief(count=3)), "nl")

    class Broken(FakeLeadAssistant):
        def lead_queries(self, *args):
            raise RuntimeError("model down")

    LeadSearch(store, Broken(), FakeSerper(), FakeFetcher()).run(list_id, "owner", "nl", "context")
    assert store.get_lead_list(list_id).status == "failed"


# --------------------------------------------------------------------------- export and retention


def test_export_keeps_text_as_text_and_links_linkedin(store):
    dangerous = LeadRow(name="=HYPERLINK(\"http://evil\")", website="https://x.example/", linkedin="https://www.linkedin.com/company/x/people/")
    content = export_xlsx(brief(), [dangerous], context_name="SAM", created_at="2026-10-07 10:00:00", expires_at="2027-01-05 10:00:00")
    sheet = load_workbook(BytesIO(content)).active
    assert sheet["B2"].value == "=HYPERLINK(\"http://evil\")"
    assert sheet["B2"].data_type == "s"
    assert sheet["H2"].hyperlink.target == "https://www.linkedin.com/company/x/people/"


def test_expired_lists_are_purged_with_their_rows(store):
    list_id = store.create_lead_list("owner", None, "ctx", "SAM", clean_brief(brief()), "nl")
    store.add_lead_row(list_id, row("5"))
    with store._connect() as connection:
        connection.execute("UPDATE lead_lists SET expires_at = datetime('now', '-1 day') WHERE id = ?", (list_id,))
    assert store.get_lead_list(list_id) is None
    assert store.purge_expired_leads() == [list_id]
    with store._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM lead_rows").fetchone()[0] == 0


# --------------------------------------------------------------------------- routes


@pytest.fixture
def app_env(monkeypatch, store):
    assistant = FakeLeadAssistant()
    started: list[tuple] = []
    monkeypatch.setenv("SIP_SESSION_SECRET", "test-secret")
    monkeypatch.setenv("SIP_COOKIE_SECURE", "false")
    monkeypatch.setenv("SIP_AUTH_EMAIL", "admin@test.nl")
    monkeypatch.setenv("SIP_AUTH_PASSWORD", "admin-pass")
    monkeypatch.setenv("SIP_AUTH_EXTRA_USERS", json.dumps(USERS))
    monkeypatch.setenv("SERPER_API_KEY", "test-serper")
    monkeypatch.setattr(main, "get_context_store", lambda: store)
    monkeypatch.setattr(main, "get_assistant", lambda: assistant)
    monkeypatch.setattr(lead_routes, "start_search", lambda *args: started.append(args))
    return store, assistant, started


def signed_in(email: str, password: str) -> TestClient:
    http = TestClient(main.app)
    assert http.post("/api/auth/login", json={"email": email, "password": password}).status_code == 200
    return http


def test_home_card_images_are_served(monkeypatch):
    monkeypatch.delenv("SIP_SESSION_SECRET", raising=False)
    http = TestClient(main.app)
    for name in ("lead-finder.webp", "lead-finder.png", "lead-finder-base.webp", "../leads.py"):
        assert http.get(f"/avatars/{name}").status_code == (404 if name.startswith("..") else 200)
    assert 'data-specialist="lead-finder"' in http.get("/").text
    assert http.get("/leads.js").status_code == 200


def test_only_sales_and_admin_reach_the_lead_finder(app_env):
    assert signed_in("po@test.nl", "po-pass").get("/api/leads/lists").status_code == 403
    assert signed_in("sales@test.nl", "sales-pass").get("/api/leads/lists").status_code == 200
    assert signed_in("admin@test.nl", "admin-pass").get("/api/leads/settings").json()["available"] is True


def test_intake_chat_keeps_the_cleaned_brief(app_env):
    store, assistant, _ = app_env
    context_id = approved_context(store)
    assistant.intake.append(LeadIntakeTurn(message="Hoeveel leads wil je?", brief=brief(count=80), ready=True))
    http = signed_in("sales@test.nl", "sales-pass")
    response = http.post("/api/leads/chat", json={"message": "Dealers in Limburg", "context_id": context_id, "language": "nl"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["brief"]["count"] == 50
    assert body["context_name"] == "SAM"
    conversation = http.get(f"/api/leads/conversations/{body['conversation_id']}").json()
    assert conversation["brief"]["count"] == 50
    assert len(conversation["messages"]) == 2
    # Another user cannot continue it.
    other = signed_in("admin@test.nl", "admin-pass")
    assert other.get(f"/api/leads/conversations/{body['conversation_id']}").status_code == 404


def test_a_website_service_is_a_starting_point_too(app_env):
    store, assistant, started = app_env
    http = signed_in("sales@test.nl", "sales-pass")
    sources = http.get("/api/leads/sources").json()
    assert sources and all(source["id"].startswith("web:") for source in sources)
    assert {"service", "product"} >= {source["offering_type"] for source in sources}
    source = sources[0]
    assistant.intake.append(LeadIntakeTurn(message="Voor wie?", brief=brief(count=None), ready=False))
    chat = http.post("/api/leads/chat", json={"message": "Gemeenten", "context_id": source["id"], "language": "nl"})
    assert chat.status_code == 200, chat.text
    assert chat.json()["context_name"] == source["name"]
    created = http.post("/api/leads/lists", json={"context_id": source["id"], "brief": brief().model_dump()})
    assert created.status_code == 201 and created.json()["context_name"] == source["name"]
    assert "reviewed website page" in started[0][4]
    # Only service and solution pages qualify; an unknown or non-offering page does not.
    assert http.post("/api/leads/lists", json={"context_id": "web:etil:does-not-exist", "brief": brief().model_dump()}).status_code == 404


def test_start_needs_a_complete_brief_and_a_real_conversation(app_env):
    store, assistant, _ = app_env
    context_id = approved_context(store)
    http = signed_in("sales@test.nl", "sales-pass")
    # The model says ready on the first turn: SIP does not believe it yet.
    assistant.intake.append(LeadIntakeTurn(message="Klaar!", brief=brief(), ready=True))
    first = http.post("/api/leads/chat", json={"message": "Dealers", "context_id": context_id}).json()
    assert first["ready"] is False
    for answer in ("Limburg", "Ja, start maar"):
        assistant.intake.append(LeadIntakeTurn(message="Volgende vraag", brief=brief(size=""), ready=True))
        turn = http.post("/api/leads/chat", json={"message": answer, "conversation_id": first["conversation_id"]}).json()
        assert turn["ready"] is False  # no size agreed
    assistant.intake.append(LeadIntakeTurn(message="Druk op Start zoeken", brief=brief(), ready=True))
    assert http.post("/api/leads/chat", json={"message": "5 vestigingen", "conversation_id": first["conversation_id"]}).json()["ready"] is True
    incomplete = {"context_id": context_id, "brief": brief(size="").model_dump()}
    assert http.post("/api/leads/lists", json=incomplete).status_code == 422


def test_briefs_saved_before_size_and_exclude_still_load():
    old = '{"title": "t", "description": "d", "industries": [], "regions": [], "extra_columns": [], "scorecard": [], "count": 5}'
    loaded = LeadBrief.model_validate_json(old)
    assert loaded.size == "" and loaded.exclude == []


def test_a_list_needs_a_count_and_never_exceeds_fifty(app_env):
    store, _, started = app_env
    context_id = approved_context(store)
    http = signed_in("sales@test.nl", "sales-pass")
    payload = {"context_id": context_id, "brief": brief(count=None).model_dump(), "language": "nl"}
    assert http.post("/api/leads/lists", json=payload).status_code == 422
    payload["brief"]["count"] = 120
    response = http.post("/api/leads/lists", json=payload)
    assert response.status_code == 201, response.text
    assert response.json()["requested"] == 50
    assert len(started) == 1
    listing = signed_in("admin@test.nl", "admin-pass").get("/api/leads/lists").json()
    assert listing[0]["mine"] is False and listing[0]["status"] == "running"
    assert listing[0]["created_by"] == "sales@test.nl"


def test_lists_from_before_created_by_still_show_their_creator(app_env):
    store, _, _ = app_env
    import hashlib
    owner = "env:" + hashlib.sha256(b"sales@test.nl").hexdigest()[:24]
    store.create_lead_list(owner, None, "ctx", "SAM", clean_brief(brief()), "nl")  # no created_by stored
    store.create_lead_list("gone", None, "ctx", "SAM", clean_brief(brief()), "nl")
    listing = signed_in("admin@test.nl", "admin-pass").get("/api/leads/lists").json()
    assert sorted(str(item["created_by"]) for item in listing) == ["None", "sales@test.nl"]


def test_no_search_without_a_serper_key(app_env, monkeypatch):
    store, _, started = app_env
    monkeypatch.delenv("SERPER_API_KEY")
    http = signed_in("sales@test.nl", "sales-pass")
    assert http.get("/api/leads/settings").json() == {"available": False, "missing": "search", "max_leads": 50, "retention_days": 90}
    payload = {"context_id": approved_context(store), "brief": brief().model_dump()}
    assert http.post("/api/leads/lists", json=payload).status_code == 503
    assert started == []


def test_scorecard_change_rescores_without_searching(app_env):
    store, _, _ = app_env
    list_id = store.create_lead_list("someone", None, "ctx", "SAM", clean_brief(brief()), "nl")
    store.add_lead_row(list_id, row("6", country="Duitsland"))
    http = signed_in("sales@test.nl", "sales-pass")
    assert http.get(f"/api/leads/lists/{list_id}").json()["rows"][0]["score"]["level"] == "medium"
    lenient = [{"column": "Vestigingen", "kind": "number", "high": "5", "medium": "2"}]
    # Someone else's list: sales may not change its scorecard, the admin may.
    assert http.put(f"/api/leads/lists/{list_id}/scorecard", json={"scorecard": lenient}).status_code == 403
    admin = signed_in("admin@test.nl", "admin-pass")
    body = admin.put(f"/api/leads/lists/{list_id}/scorecard", json={"scorecard": lenient}).json()
    assert body["rows"][0]["score"]["level"] == "high"
    assert body["counts"] == {"high": 1, "medium": 0, "low": 0}
    export = http.get(f"/api/leads/lists/{list_id}/export?language=nl")
    assert export.headers["content-type"].startswith("application/vnd.openxmlformats")
    # Only the creator or an admin deletes.
    assert http.delete(f"/api/leads/lists/{list_id}").status_code == 404
    assert signed_in("admin@test.nl", "admin-pass").delete(f"/api/leads/lists/{list_id}").status_code == 204


# --------------------------------------------------------------------------- Dify


def test_dify_lead_tasks_go_to_the_lead_finder_app(monkeypatch):
    for name, value in {
        "DIFY_STRATEGIST_API_KEY": "a", "DIFY_FINALIZER_API_KEY": "b", "DIFY_KNOWLEDGE_API_KEY": "c", "DIFY_DATASET_API_KEY": "d",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("DIFY_LEAD_FINDER_API_KEY", raising=False)
    assert DifyAssistant().lead_available() is False
    with pytest.raises(AssistantUnavailable):
        DifyAssistant().lead_queries("{}", "[]", "nl", "owner")

    monkeypatch.setenv("DIFY_LEAD_FINDER_API_KEY", "app-leads")
    sent: list[httpx.Request] = []

    def handler(request):
        sent.append(request)
        return httpx.Response(200, json={"answer": '{"queries": [{"query": "dealer limburg", "country": "nl"}]}'})

    dify = DifyAssistant()
    dify.http = httpx.Client(transport=httpx.MockTransport(handler))
    plan = dify.lead_queries('{"description": "dealers"}', "[]", "nl", "owner")
    assert plan.queries[0].query == "dealer limburg"
    body = json.loads(sent[0].content)
    assert sent[0].headers["Authorization"] == "Bearer app-leads"
    assert body["inputs"]["task"] == "queries"
    assert "dealers" in body["inputs"]["payload"]
    assert body["user"] != "owner"  # pseudonym, never SIP's user id


def test_one_search_at_a_time_and_a_daily_limit(app_env, monkeypatch):
    store, _, _ = app_env
    context_id = approved_context(store)
    http = signed_in("sales@test.nl", "sales-pass")
    payload = {"context_id": context_id, "brief": brief().model_dump()}
    assert http.post("/api/leads/lists", json=payload).status_code == 201
    assert http.post("/api/leads/lists", json=payload).status_code == 429  # the first one still runs
    with store._connect() as connection:
        connection.execute("UPDATE lead_lists SET status = 'done'")
    monkeypatch.setattr(lead_routes, "DAILY_LEAD_SEARCHES", 1)
    assert http.post("/api/leads/lists", json=payload).status_code == 429


def test_a_busy_ai_service_is_retried_and_then_counted_as_skipped(store, monkeypatch):
    from app import lead_search
    monkeypatch.setattr(lead_search, "RETRY_SECONDS", 0)
    list_id = store.create_lead_list("owner", None, "ctx", "SAM", clean_brief(brief(count=2)), "nl")

    class Busy(FakeLeadAssistant):
        def lead_extract(self, *args):
            raise AssistantUnavailable("Dify is busy")

    LeadSearch(store, Busy(), FakeSerper(), FakeFetcher()).run(list_id, "owner", "nl", "context")
    record = store.get_lead_list(list_id)
    assert record.rows == [] and record.skipped == 6


def test_a_city_that_is_not_on_its_page_is_dropped():
    pages = {"https://x.example/": "Wij zitten in Sittard"}
    extraction = LeadExtraction(
        fits=True, name="X", city=LeadFact(value="Maastricht", source="https://x.example/"),
        country=LeadFact(), phone=LeadFact(), email=LeadFact(), extra=[], why_fits="",
    )
    assert build_row(LeadCandidate(name="X", website="https://x.example"), pages, extraction, []).city.value is None


def test_linkedin_rejects_namesakes_and_requires_exact_company_website():
    class EvidenceSearch:
        def search(self, *args, **kwargs):
            return [SearchResult("Essent", "https://www.linkedin.com/company/essent-us", "Website essent.us"),
                    SearchResult("Essent", "https://www.linkedin.com/company/essent-fake", "Website notessent.nl"),
                    SearchResult("Essent", "https://nl.linkedin.com/company/essent", "Website https://www.essent.nl/")]
    search = LeadSearch(None, None, EvidenceSearch(), None)
    assert search._linkedin("Essent", "Nederland", "https://www.essent.nl") == "https://www.linkedin.com/company/essent/people/"
    class NoEvidence:
        def search(self, *args, **kwargs):
            return [SearchResult("Essent", "https://www.linkedin.com/company/essent-us", "Energy company")]
    search.serper = NoEvidence()
    assert search._linkedin("Essent", "Nederland", "https://essent.nl") is None
    assert search._linkedin("Essent", "Nederland") is None


def test_keyword_score_handles_intervening_words_without_negation_or_substring_false_positives():
    from app.leads import _criterion_level, ScoreCriterion
    criterion = ScoreCriterion(column="Klantenservice", kind="keyword", high="expliciete zakelijke klantenservice", medium="algemene klantenservice")
    assert _criterion_level(criterion, "Expliciete algemene klantenservice en zakelijke klantenservice aantoonbaar") == "high"
    assert _criterion_level(criterion, "Geen expliciete zakelijke klantenservice, maar algemene klantenservice") == "medium"
    assert _criterion_level(criterion, "Niet expliciete zakelijke klantenservice") == "low"
    assert _criterion_level(criterion, None) == "unknown"
    short = ScoreCriterion(column="Energie", kind="keyword", high="gas", medium="elektriciteit")
    assert _criterion_level(short, "Veel gasten") == "low"
    assert _criterion_level(short, "Gas en elektriciteit") == "high"
    absence = ScoreCriterion(column="Chat", kind="keyword", high="geen chatbot", medium="chatbot")
    assert _criterion_level(absence, "Geen chatbot gedetecteerd") == "high"
