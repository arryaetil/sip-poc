"""Server messages follow the language SIP is shown in."""

import json

from fastapi.testclient import TestClient

from app import main
from app.messages import EXACT, translate


def test_known_messages_are_translated_and_unknown_ones_stay_english():
    assert translate("Incorrect email or password", "nl") == "Onjuist e-mailadres of wachtwoord."
    assert translate("Incorrect email or password", "de") == "E-Mail-Adresse oder Passwort ist falsch."
    assert translate("Incorrect email or password", "en") == "Incorrect email or password"
    assert translate("This story was already created in Azure DevOps as #4242.", "nl") == (
        "Deze story is al aangemaakt in Azure DevOps als #4242."
    )
    assert translate("Something nobody wrote down", "nl") == "Something nobody wrote down"
    assert translate(["not", "a", "string"], "nl") == ["not", "a", "string"]
    assert all(dutch and german for dutch, german in EXACT.values())


def test_errors_and_the_login_gate_answer_in_the_interface_language(monkeypatch):
    monkeypatch.setenv("SIP_SESSION_SECRET", "test-secret")
    monkeypatch.setenv("SIP_AUTH_EMAIL", "admin@test.nl")
    monkeypatch.setenv("SIP_AUTH_PASSWORD", "admin-pass")
    monkeypatch.setenv("SIP_AUTH_EXTRA_USERS", json.dumps({}))
    http = TestClient(main.app)
    wrong = http.post("/api/auth/login", json={"email": "admin@test.nl", "password": "nope"}, headers={"X-SIP-Language": "nl"})
    assert wrong.status_code == 401 and wrong.json()["detail"] == "Onjuist e-mailadres of wachtwoord."
    gate = http.get("/api/contexts", headers={"X-SIP-Language": "de"})
    assert gate.json()["detail"] == "Bitte melde dich zuerst an."
    english = http.get("/api/contexts")
    assert english.json()["detail"] == "Authentication required"
    invalid = http.post("/api/auth/login", json={"email": "x"}, headers={"X-SIP-Language": "nl"})
    assert invalid.status_code == 422
    assert invalid.json()["detail"] == "Er ontbreekt informatie of iets is niet geldig."
    assert invalid.json()["errors"]
