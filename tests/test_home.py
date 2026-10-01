from fastapi.testclient import TestClient

from app import main


def client(monkeypatch) -> TestClient:
    monkeypatch.delenv("SIP_SESSION_SECRET", raising=False)
    return TestClient(main.app)


def test_home_images_are_served_and_unknown_files_are_refused(monkeypatch):
    http = client(monkeypatch)
    for name in ("marketing", "kennis", "kyc"):
        assert http.get(f"/avatars/{name}.webp").status_code == 200
        assert http.get(f"/avatars/{name}.png").headers["content-type"] == "image/png"
    assert http.get("/avatars/../main.py").status_code == 404
    assert http.get("/avatars/marketing.exe").status_code == 404
    assert http.get("/avatars/other.png").status_code == 404


def test_index_only_offers_videos_that_exist(monkeypatch, tmp_path):
    http = client(monkeypatch)
    assert 'data-video="/avatars/marketing.mp4"' not in http.get("/").text

    for name in ("marketing", "kennis", "kyc"):
        for extension in ("png", "webp"):
            (tmp_path / f"{name}.{extension}").write_bytes((main.AVATAR_DIR / f"{name}.{extension}").read_bytes())
    (tmp_path / "marketing.mp4").write_bytes(b"\x00")
    monkeypatch.setattr(main, "AVATAR_DIR", tmp_path)
    page = http.get("/").text
    assert 'data-video="/avatars/marketing.mp4"' in page
    assert 'data-video="/avatars/kyc.mp4"' not in page


def test_fonts_are_public_but_whitelisted(monkeypatch):
    monkeypatch.setenv("SIP_SESSION_SECRET", "test-secret")
    http = TestClient(main.app)
    assert http.get("/fonts/ubuntu-regular.woff2").status_code == 200
    assert http.get("/fonts/UFL.txt").status_code == 404
    assert http.get("/avatars/marketing.webp", follow_redirects=False).status_code == 303
