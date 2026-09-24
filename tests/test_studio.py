import base64
import hashlib
import hmac
import json
import time

import pytest
import httpx

from app import studio
from app.models import KnowledgeChatSource, MarketingRequest


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("OPEN_DESIGN_INTERNAL_URL", "http://od.internal:8080")
    monkeypatch.setenv("OPEN_DESIGN_PUBLIC_URL", "https://studio.example")
    monkeypatch.setenv("OPEN_DESIGN_TOKEN", "od-token")
    monkeypatch.setenv("STUDIO_HANDOFF_SECRET", "s3cret")


def test_signed_link_matches_what_the_gateway_verifies(configured):
    link = studio.signed_link("alice", "/projects/sip-1")
    assert link.startswith("https://studio.example/__sip/enter?t=")
    body, signature = link.split("t=", 1)[1].split(".")
    # gateway.mjs: base64url HMAC-SHA256 of the body, no padding
    expected = base64.urlsafe_b64encode(hmac.new(b"s3cret", body.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    assert signature == expected
    claims = json.loads(base64.urlsafe_b64decode(body + "=="))
    assert claims["next"] == "/projects/sip-1"
    assert claims["sub"] != "alice"  # a pseudonym, not the SIP user id
    assert 0 < claims["exp"] - time.time() <= studio.LINK_SECONDS


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


def test_private_brand_library_is_not_copied_into_every_project():
    requested = []

    def handle(request):
        requested.append((request.method, request.url.path, request.url.params.get("path")))
        if request.url.path.endswith("/files") and request.method == "GET":
            return httpx.Response(200, json={"files": [
                {"path": "assets/private-library/large-original.jpg"},
                {"path": "assets/images/approved.jpg"},
            ]})
        if request.url.path.endswith("/static"):
            return httpx.Response(200, content=b"image", headers={"content-type": "image/jpeg"})
        return httpx.Response(201)

    with httpx.Client(base_url="https://studio.example", transport=httpx.MockTransport(handle)) as client:
        studio._copy_brand_assets(client, "user:etil", "example")

    assert ("GET", "/api/design-systems/user:etil/static", "assets/private-library/large-original.jpg") not in requested
    assert ("GET", "/api/design-systems/user:etil/static", "assets/images/approved.jpg") in requested
    assert sum(method == "POST" for method, _, _ in requested) == 1
