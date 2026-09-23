import json

import httpx
import pytest

from app import assistants
from app.assistants import AssistantUnavailable, DifyAssistant, get_assistant
from app.models import ConversationMessage

KEYS = {
    "DIFY_STRATEGIST_API_KEY": "app-strategist",
    "DIFY_FINALIZER_API_KEY": "app-finalizer",
    "DIFY_KNOWLEDGE_API_KEY": "app-knowledge",
    "DIFY_DATASET_API_KEY": "dataset-kb",
}

HISTORY = [
    ConversationMessage(id=1, role="user", content="We build a housing dashboard", created_at="t"),
    ConversationMessage(id=2, role="assistant", content="Who uses it?", created_at="t"),
]


@pytest.fixture
def dify(monkeypatch):
    """A DifyAssistant whose HTTP calls land in `sent` and get `reply` back."""
    for name, value in KEYS.items():
        monkeypatch.setenv(name, value)
    sent: list[httpx.Request] = []
    reply: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json=reply)

    assistant = DifyAssistant()
    assistant.http = httpx.Client(transport=httpx.MockTransport(handler))
    return assistant, sent, reply


@pytest.fixture
def knowledge_base(dify):
    """The Dify knowledge base client, answering like the real API."""
    assistant, _, _ = dify
    calls: list[tuple[str, str, dict]] = []
    documents: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        path = request.url.path.split("/datasets/", 1)[1].split("/", 1)[1]
        calls.append((request.method, path, body))
        if path == "metadata":
            return httpx.Response(200, json={"doc_metadata": [{"id": "field-1", "name": "owner"}]})
        if path == "documents" and request.method == "GET":
            keyword = request.url.params["keyword"]
            return httpx.Response(200, json={"data": [d for d in documents if keyword in d["name"]]})
        if path == "document/create-by-text":
            documents.append({"id": f"doc-{len(documents)}", "name": body["name"]})
            return httpx.Response(200, json={"document": documents[-1]})
        return httpx.Response(200, json={})

    assistant.knowledge_base.http = httpx.Client(
        base_url="https://dify.test/v1", transport=httpx.MockTransport(handler)
    )
    return assistant, calls, documents


def test_dify_refuses_to_start_without_every_key(monkeypatch):
    monkeypatch.setenv("SIP_ASSISTANT_PROVIDER", "dify")
    monkeypatch.setenv("DIFY_STRATEGIST_API_KEY", "app-x")
    monkeypatch.delenv("DIFY_FINALIZER_API_KEY", raising=False)
    monkeypatch.delenv("DIFY_KNOWLEDGE_API_KEY", raising=False)
    get_assistant.cache_clear()
    try:
        with pytest.raises(AssistantUnavailable, match="DIFY_FINALIZER_API_KEY"):
            get_assistant()
    finally:
        get_assistant.cache_clear()


def test_unknown_provider_is_rejected(monkeypatch):
    monkeypatch.setenv("SIP_ASSISTANT_PROVIDER", "openai")
    get_assistant.cache_clear()
    try:
        with pytest.raises(AssistantUnavailable):
            get_assistant()
    finally:
        get_assistant.cache_clear()


def test_strategist_turn_sends_history_and_parses_json(dify):
    assistant, sent, reply = dify
    reply["answer"] = json.dumps(
        {"message": "Tell me more", "is_ready_to_save": False, "readiness_reason": "No customers yet"}
    )

    turn = assistant.strategist_turn(HISTORY, "Municipalities", "nl", "alice")

    assert turn.message == "Tell me more"
    body = json.loads(sent[0].content)
    assert sent[0].headers["authorization"] == "Bearer app-strategist"
    assert body["query"] == "Municipalities"
    assert body["inputs"]["language"] == "Dutch"
    assert "User: We build a housing dashboard" in body["inputs"]["history"]
    assert "Assistant: Who uses it?" in body["inputs"]["history"]
    # Dify gets a stable pseudonym, never SIP's user id.
    assert body["user"] != "alice" and len(body["user"]) == 24


def test_invalid_json_is_an_error_not_a_blank_turn(dify):
    assistant, _, reply = dify
    reply["answer"] = "Sure! Here is your answer."
    with pytest.raises(ValueError):
        assistant.strategist_turn(HISTORY, "hi", "en", "alice")


def test_knowledge_answer_maps_dify_files_to_sip_sources(dify, monkeypatch):
    assistant, sent, reply = dify
    monkeypatch.setattr(
        assistants,
        "_documents_by_filename",
        lambda: {"solution-de-woonatlas.md": ("De WoonAtlas - Etil", "https://etil.nl/de-woonatlas/")},
    )
    reply.update(
        {
            "answer": "De WoonAtlas is een beleidsplatform.",
            "message_id": "m1",
            "metadata": {
                "retriever_resources": [
                    {"document_name": "solution-de-woonatlas.md", "score": 0.78},
                    {"document_name": "solution-de-woonatlas.md", "score": 0.77},
                ]
            },
        }
    )

    answer = assistant.knowledge_answer(HISTORY, "Wat is de WoonAtlas?", "nl", "alice", False)

    assert answer.message.startswith("De WoonAtlas")
    assert [(s.title, s.url) for s in answer.sources] == [("De WoonAtlas - Etil", "https://etil.nl/de-woonatlas/")]
    assert json.loads(sent[0].content)["inputs"]["general"] == "no"


def owners_set(calls):
    return [
        item["metadata_list"][0]["value"]
        for method, path, body in calls
        if path == "documents/metadata"
        for item in body["operation_data"]
    ]


def test_private_upload_is_labelled_with_its_owner_only(knowledge_base):
    assistant, calls, documents = knowledge_base
    assistant.index_upload(upload_id="u1", owner_id="alice", filename="offer.pdf", content="text", visibility="private")

    assert documents[0]["name"] == "upload:u1:offer.pdf"
    assert owners_set(calls) == [assistants._owner_label("alice")]
    assert "alice" not in json.dumps([body for _, _, body in calls])


def test_published_evidence_becomes_public(knowledge_base):
    assistant, calls, _ = knowledge_base
    assistant.index_upload(upload_id="u1", owner_id="alice", filename="offer.pdf", content="text", visibility="private")
    assistant.set_upload_visibility("u1", "org", "alice")
    assert owners_set(calls)[-1] == "public"


def test_context_is_private_until_approved_and_updates_in_place(knowledge_base):
    from app.models import StoredBusinessContext
    from test_workspaces import context

    assistant, calls, documents = knowledge_base
    draft = StoredBusinessContext(**context("SIP").model_dump(), id="c1", status="draft", created_at="t", updated_at="t")
    assistant.index_context(draft, "alice")
    assistant.index_context(draft.model_copy(update={"status": "approved"}), "alice")

    assert len(documents) == 1  # the second save updated the same document
    assert any(path == "documents/doc-0/update-by-text" for _, path, _ in calls)
    assert owners_set(calls) == [assistants._owner_label("alice"), "public"]


def test_knowledge_request_carries_the_owner_filter_value(dify):
    assistant, sent, reply = dify
    reply["answer"] = json.dumps({"message": "Hi", "answered_from_sources": False})
    assistant.knowledge_answer([], "Hoi", "nl", "alice", False)
    assert json.loads(sent[0].content)["inputs"]["owner"] == assistants._owner_label("alice")


def test_upload_and_context_sources_map_back_to_sip():
    assert assistants._source_for("upload:u1:offer.pdf", {}) == ("offer.pdf", "/api/uploads/u1")
    assert assistants._source_for("context:c1:SIP", {}) == ("SIP", "")


def test_knowledge_lists_no_sources_when_the_corpus_has_no_answer(dify):
    assistant, _, reply = dify
    reply.update(
        {
            "answer": json.dumps({"message": "Dat staat niet op de website.", "answered_from_sources": False}),
            "metadata": {"retriever_resources": [{"document_name": "home.md", "score": 0.65}]},
        }
    )
    answer = assistant.knowledge_answer([], "Wie is de CEO?", "nl", "alice", False)
    assert answer.message == "Dat staat niet op de website."
    assert answer.sources == []


def test_long_history_drops_the_oldest_messages():
    history = [
        ConversationMessage(id=i, role="user", content=f"m{i} " + "x" * 1000, created_at="t") for i in range(200)
    ]
    text = assistants._transcript(history, limit=10_000)
    assert len(text) < 10_000
    assert text.startswith(assistants.OMITTED)
    assert "m199 " in text and "m0 " not in text
