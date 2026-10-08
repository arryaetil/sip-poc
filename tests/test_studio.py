import base64
import hashlib
import hmac
import json
import time

import pytest
import httpx

from app import studio
from app.models import KnowledgeChatSource, MarketingRequest


def test_handoff_keeps_approved_carousel_instead_of_short_linkedin_offer():
    from types import SimpleNamespace
    hook = "Wie de arbeidsmarkt wil versterken, moet eerst weten wat er speelt."
    brief = hook + "\n" + "\n".join(f"Pagina {i}: afgesproken inhoud {i}" for i in range(1, 7))
    calls = []
    class Assistant:
        def strategist_turn(self, *args):
            calls.append(args)
            return SimpleNamespace(message=json.dumps(dict(format="instagram_carousel", brief=brief, title="AIZ", brand="etil")))
    history = [SimpleNamespace(content="six approved pages")]
    request = studio.prepare_brief(Assistant(), MarketingRequest(format="linkedin_post", brief="Kort AIZ"), history, "nl", "alice")
    assert request.format == "instagram_carousel"
    assert hook in request.brief and "Pagina 6:" in request.brief
    assert calls[0][0] is history
    assert "page count/order" in calls[0][4]
    text = studio.context_document(request, [SimpleNamespace(content="private@example.org")], [])
    assert "private@example.org" not in text
    assert brief in text


def test_handoff_refuses_invalid_response_instead_of_silent_brief_loss():
    from types import SimpleNamespace
    assistant = SimpleNamespace(strategist_turn=lambda *args: SimpleNamespace(message="Looks good!"))
    with pytest.raises(ValueError):
        studio.prepare_brief(assistant, MarketingRequest(format="linkedin_post", brief="AIZ"), [object()], "nl", "alice")


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("OPEN_DESIGN_INTERNAL_URL", "http://od.internal:8080")
    monkeypatch.setenv("OPEN_DESIGN_PUBLIC_URL", "https://studio.example")
    monkeypatch.setenv("OPEN_DESIGN_TOKEN", "od-token")
    monkeypatch.setenv("STUDIO_HANDOFF_SECRET", "s3cret")


def test_signed_link_matches_what_the_gateway_verifies(configured):
    link = studio.signed_link("alice", "/projects/sip-1", "de")
    assert link.startswith("https://studio.example/__sip/enter?t=")
    body, signature = link.split("t=", 1)[1].split(".")
    # gateway.mjs: base64url HMAC-SHA256 of the body, no padding
    expected = base64.urlsafe_b64encode(hmac.new(b"s3cret", body.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    assert signature == expected
    claims = json.loads(base64.urlsafe_b64decode(body + "=="))
    assert claims["next"] == "/projects/sip-1"
    assert claims["lang"] == "de"
    assert claims["sub"] != "alice"  # a pseudonym, not the SIP user id
    assert 0 < claims["exp"] - time.time() <= studio.LINK_SECONDS


def test_signed_link_rejects_unsupported_language_by_using_dutch(configured):
    link = studio.signed_link("alice", language="<script>")
    body = link.split("t=", 1)[1].split(".")[0]
    assert json.loads(base64.urlsafe_b64decode(body + "=="))["lang"] == "nl"


def test_unconfigured_studio_is_unavailable(monkeypatch):
    monkeypatch.delenv("OPEN_DESIGN_TOKEN", raising=False)
    with pytest.raises(studio.StudioUnavailable):
        studio.signed_link("alice")


def test_context_document_carries_only_supplied_facts():
    text = studio.context_document(
        MarketingRequest(format="linkedin_post", brief="Post over de WoonAtlas"),
        [],
        [KnowledgeChatSource(title="De WoonAtlas - Etil", url="https://etil.nl/de-woonatlas/", passages=["Een beleidsplatform."])],
    )
    assert "Do not invent" in text
    assert "> Een beleidsplatform." in text
    assert "https://etil.nl/de-woonatlas/" in text


def test_project_points_at_the_brand_folder_the_gateway_fills(configured, monkeypatch):
    # The gateway copies the brand files (gateway.mjs, test-gateway.mjs); SIP only
    # creates the project and its context file, and names the same brand/etil/ folder.
    requested = []

    def handle(request):
        requested.append((request.method, request.url.path, request.content))
        return httpx.Response(201, json={})

    real_client = httpx.Client
    monkeypatch.setattr(studio.httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(handle), **kwargs))
    link = studio.create_project("alice", MarketingRequest(format="linkedin_post", brief="People Service"), [], [])

    assert link.startswith("https://studio.example/__sip/enter?t=")
    assert [(method, path) for method, path, _ in requested][0] == ("POST", "/api/projects")
    assert [path for _, path, _ in requested[1:]] == [f"{requested[0][1]}/{json.loads(requested[0][2])['id']}/files"]
    project = json.loads(requested[0][2])
    assert project["designSystemId"] == "user:etil"
    assert "brand/etil/fonts/Ubuntu-" in project["customInstructions"]
    assert project["pendingPrompt"] == "People Service"
    assert "user:etil" not in project["pendingPrompt"]
