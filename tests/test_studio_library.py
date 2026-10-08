import hashlib
import hmac
import time
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import main, studio
from app.models import StoredBusinessContext, BusinessContext


def headers(secret="test-handoff", timestamp=None):
    timestamp = str(timestamp if timestamp is not None else int(time.time()))
    return {"x-sip-library-time": timestamp, "x-sip-library-signature": hmac.new(secret.encode(), f"sip-studio-library\n{timestamp}".encode(), hashlib.sha256).hexdigest()}


def context(name="SAM", status="approved"):
    data = {key: [] for key in BusinessContext.model_fields}
    data.update(name=name, offering_type="service", short_summary="Smart Service Center", value_proposition="Betere intake", people=["Do not export this person"])
    return StoredBusinessContext(**data, id="context-1", status=status, created_at="2026-10-08", updated_at="2026-10-08")


def test_server_library_requires_fresh_valid_signature(monkeypatch):
    monkeypatch.setenv("STUDIO_HANDOFF_SECRET", "test-handoff")
    assert studio.library_authorised(headers())
    assert not studio.library_authorised(headers("wrong"))
    assert not studio.library_authorised(headers(timestamp=int(time.time()) - 90))
    assert not studio.library_authorised(headers(timestamp=int(time.time()) + 90))
    assert not studio.library_authorised({"x-sip-library-time": "9" * 5000, "x-sip-library-signature": "é" * 64})
    monkeypatch.delenv("STUDIO_HANDOFF_SECRET")
    assert not studio.library_authorised(headers())


def test_library_contains_only_current_approved_shared_contexts(monkeypatch):
    current = context()
    class Store:
        def list(self, owner_id, approved_only):
            assert approved_only
            return [SimpleNamespace(id="context-1"), SimpleNamespace(id="draft-1")]
        def get(self, id, owner_id): return current if id == "context-1" else context("Draft", "draft")
    website = SimpleNamespace(title="SAM case", canonical_url="https://example.test/sam", organisation="ibc group", source_id="ibc:sam", content="Published case facts")
    first = studio.library_documents(Store(), [website])
    text = "\n".join(file["content"] for file in first["files"])
    assert "SAM" in text and "https://example.test/sam" in text
    assert "Draft" not in text and "Do not export this person" not in text
    current = context("Changed SAM")
    assert studio.library_documents(Store(), [website])["revision"] != first["revision"]
    current = context("Deleted", "draft")
    updated = studio.library_documents(Store(), [website])
    assert "## SAM" not in updated["files"][0]["content"]
    assert updated["revision"] != first["revision"]


def test_library_endpoint_works_only_for_server_and_other_routes_stay_protected(monkeypatch):
    monkeypatch.setenv("SIP_SESSION_SECRET", "test-session")
    monkeypatch.setenv("STUDIO_HANDOFF_SECRET", "test-handoff")
    monkeypatch.setattr(studio, "library_documents", lambda *args: {"revision": "test", "files": []})
    client = TestClient(main.app)
    assert client.get(studio.LIBRARY_PATH).status_code == 401
    assert client.get(studio.LIBRARY_PATH, headers=headers("wrong")).status_code == 401
    assert client.get(studio.LIBRARY_PATH, headers=headers()).status_code == 200
    assert client.get("/api/contexts", headers=headers()).status_code == 401
    assert client.post(studio.LIBRARY_PATH, headers=headers()).status_code == 401
