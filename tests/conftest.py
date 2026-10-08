"""Shared test setup."""

import pytest


@pytest.fixture(autouse=True)
def local_development(monkeypatch):
    # Without a session secret SIP refuses to run, except in explicit local development.
    monkeypatch.setenv("SIP_LOCAL_DEV", "1")
