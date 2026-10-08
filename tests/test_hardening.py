"""Hardening: sign-in fails closed, security headers, login throttling, unreadable uploads."""

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from app import main
from app.uploads import extract_text

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.fixture
def signed_in_app(monkeypatch):
    monkeypatch.setenv("SIP_SESSION_SECRET", "test-secret")
    monkeypatch.setenv("SIP_COOKIE_SECURE", "false")
    monkeypatch.setenv("SIP_AUTH_EMAIL", "admin@test.nl")
    monkeypatch.setenv("SIP_AUTH_PASSWORD", "admin-pass")
    monkeypatch.setenv("SIP_AUTH_EXTRA_USERS", json.dumps({}))
    monkeypatch.setattr(main, "_login_failures", {})
    return TestClient(main.app)


def test_without_a_session_secret_sip_refuses_instead_of_letting_everyone_in(monkeypatch):
    monkeypatch.delenv("SIP_SESSION_SECRET", raising=False)
    monkeypatch.delenv("SIP_LOCAL_DEV", raising=False)
    http = TestClient(main.app)
    assert http.get("/api/contexts").status_code == 503
    assert http.get("/").status_code == 503
    assert http.get("/health").status_code == 200  # Railway's health check stays public
    monkeypatch.setenv("SIP_LOCAL_DEV", "1")
    assert http.get("/api/contexts").status_code == 200


def test_pages_carry_security_headers(signed_in_app, monkeypatch):
    monkeypatch.setenv("OPEN_DESIGN_PUBLIC_URL", "https://studio.example")
    headers = signed_in_app.get("/login").headers
    policy = headers["content-security-policy"]
    assert "frame-ancestors 'none'" in policy and "script-src 'self'" in policy
    assert "frame-src 'self' https://studio.example" in policy
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "<script>" not in signed_in_app.get("/login").text  # no inline script under this policy
    assert signed_in_app.get("/login.js").status_code == 200


def test_repeated_wrong_passwords_are_slowed_down(signed_in_app, monkeypatch):
    monkeypatch.setattr(main.time, "sleep", lambda seconds: None)
    for _ in range(main.LOGIN_MAX_FAILURES):
        assert signed_in_app.post("/api/auth/login", json={"email": "admin@test.nl", "password": "wrong"}).status_code == 401
    blocked = signed_in_app.post("/api/auth/login", json={"email": "admin@test.nl", "password": "admin-pass"})
    assert blocked.status_code == 429
    monkeypatch.setattr(main, "_login_failures", {})
    assert signed_in_app.post("/api/auth/login", json={"email": "admin@test.nl", "password": "admin-pass"}).status_code == 200


def test_legacy_routes_around_the_provider_seam_are_gone(signed_in_app):
    signed_in_app.post("/api/auth/login", json={"email": "admin@test.nl", "password": "admin-pass"})
    assert signed_in_app.post("/api/chat", json={"message": "hi"}).status_code in (404, 405)
    assert signed_in_app.post("/api/contexts/prepare", json={"previous_response_id": "x"}).status_code in (404, 405)


def test_damaged_and_oversized_documents_are_refused_politely():
    with pytest.raises(ValueError, match="could not be read"):
        extract_text(b"%PDF-1.4 not really a pdf", "application/pdf")
    bomb = io.BytesIO()
    with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", b"0" * (61 * 1024 * 1024))
    with pytest.raises(ValueError, match="too large once unpacked"):
        extract_text(bomb.getvalue(), DOCX)
