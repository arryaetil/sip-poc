import base64
import json
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient

from app import developer, main


def test_link_requires_login_and_exact_account(monkeypatch, tmp_path):
    monkeypatch.setenv("SIP_DB_PATH", str(tmp_path / "sip.db"))
    main.get_context_store.cache_clear()
    monkeypatch.setenv("SIP_AUTH_EMAIL", "arrya@example.test")
    monkeypatch.setenv("SIP_AUTH_PASSWORD", "test-password")
    monkeypatch.setenv("SIP_SESSION_SECRET", "test-session")
    monkeypatch.setenv("SIP_COOKIE_SECURE", "false")
    monkeypatch.setenv("SIP_DEVELOPER_EMAIL", "arrya@example.test")
    monkeypatch.setenv("OPENCODE_DEVELOPER_PUBLIC_URL", "https://developer.example.test")
    monkeypatch.setenv("DEVELOPER_HANDOFF_SECRET", "test-handoff")
    with TestClient(main.app) as client:
        assert client.get("/api/developer/link").status_code == 401
        client.post("/api/auth/login", json={"email": "arrya@example.test", "password": "test-password"})
        assert client.get("/api/developer/availability").json() == {"available": True}
        url = client.get("/api/developer/link").json()["url"]
        token = parse_qs(urlsplit(url).query)["t"][0]
        body, signature = token.split(".")
        assert signature and json.loads(base64.urlsafe_b64decode(body + "=="))["jti"]
        assert url.startswith("https://developer.example.test/__sip/enter?t=")
    main.get_context_store.cache_clear()


def test_other_account_and_missing_configuration(monkeypatch, tmp_path):
    monkeypatch.setenv("SIP_DB_PATH", str(tmp_path / "sip.db"))
    main.get_context_store.cache_clear()
    monkeypatch.setenv("SIP_AUTH_EMAIL", "other@example.test")
    monkeypatch.setenv("SIP_AUTH_PASSWORD", "test-password")
    monkeypatch.setenv("SIP_SESSION_SECRET", "test-session")
    monkeypatch.setenv("SIP_COOKIE_SECURE", "false")
    monkeypatch.setenv("SIP_DEVELOPER_EMAIL", "arrya@example.test")
    monkeypatch.setenv("OPENCODE_DEVELOPER_PUBLIC_URL", "https://developer.example.test")
    monkeypatch.setenv("DEVELOPER_HANDOFF_SECRET", "test-handoff")
    with TestClient(main.app) as client:
        client.post("/api/auth/login", json={"email": "other@example.test", "password": "test-password"})
        assert client.get("/api/developer/availability").json() == {"available": False}
        assert client.get("/api/developer/link").status_code == 403
        monkeypatch.delenv("DEVELOPER_HANDOFF_SECRET")
        assert client.get("/api/developer/link").status_code == 503
        assert client.get("/").status_code == 200
    main.get_context_store.cache_clear()


def test_home_has_developer_avatar_and_new_tab_action(monkeypatch):
    monkeypatch.delenv("SIP_SESSION_SECRET", raising=False)
    with TestClient(main.app) as client:
        page = client.get("/").text
        assert 'data-specialist="developer"' in page
        assert 'data-developer-open' in page
        assert client.get("/avatars/developer.webp").status_code == 200
        assert client.get("/avatars/developer.png").status_code == 200


def test_link_signing_refuses_unconfigured_or_wrong_account(monkeypatch):
    monkeypatch.delenv("DEVELOPER_HANDOFF_SECRET", raising=False)
    try:
        developer.signed_link("arrya@example.test")
    except developer.DeveloperUnavailable:
        pass
    else:
        assert False
