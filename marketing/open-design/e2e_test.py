"""End-to-end check of the Marketing studio against the live services.

Creates a project the way SIP does (house style, brief, context.md), starts a
run through the gateway the way the browser does, waits for it and lists the
files Open Design produced.

    cd backend && python ../marketing/open-design/e2e_test.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))
load_dotenv(BACKEND / ".env")
# From the laptop the private network is unreachable; use the public gateway.
os.environ.setdefault("OPEN_DESIGN_INTERNAL_URL", os.environ["OPEN_DESIGN_PUBLIC_URL"])

from app import studio  # noqa: E402
from app.models import KnowledgeChatSource, MarketingRequest  # noqa: E402

BASE = os.environ["OPEN_DESIGN_PUBLIC_URL"].rstrip("/")
HEADERS = {"Authorization": f"Bearer {os.environ['OPEN_DESIGN_TOKEN']}"}


def main() -> None:
    request = MarketingRequest(
        format="linkedin_post",
        brief="LinkedIn-post over de WoonAtlas voor gemeenten",
        title="E2E-test WoonAtlas LinkedIn-post",
    )
    sources = [
        KnowledgeChatSource(
            title="De WoonAtlas - Etil",
            url="https://etil.nl/de-woonatlas/",
            passages=[
                "De WoonAtlas brengt data, analyses en prognoses samen in één integraal beleidsplatform, "
                "zodat overheden, woningcorporaties en maatschappelijke organisaties beschikken over een "
                "betrouwbaar fundament voor toekomstbestendig woningmarktbeleid."
            ],
        )
    ]
    link = studio.create_project("e2e-test", request, [], sources)
    project_id = link.split("next")[0] and json.loads(
        __import__("base64").urlsafe_b64decode(link.split("t=")[1].split(".")[0] + "==")
    )["next"].rsplit("/", 1)[1]
    print("project:", project_id)

    with httpx.Client(base_url=BASE, headers=HEADERS, timeout=60) as http:
        project = http.get(f"/api/projects/{project_id}").json()
        prompt = (project.get("project") or project).get("pendingPrompt") or request.brief
        started = http.post("/api/runs", json={"projectId": project_id, "message": prompt, "conversationId": None})
        print("start run:", started.status_code, started.text[:300])
        started.raise_for_status()
        run_id = started.json().get("runId") or started.json().get("id") or started.json().get("run", {}).get("id")
        deadline = time.time() + 600
        status = None
        while time.time() < deadline:
            run = http.get(f"/api/runs/{run_id}").json()
            status = (run.get("run") or run).get("status")
            if status in ("succeeded", "completed", "failed", "error", "cancelled", "canceled"):
                break
            time.sleep(10)
        print("run status:", status)
        print("run detail:", json.dumps(run)[:1200])
        files = http.get(f"/api/projects/{project_id}/files").json().get("files", [])
        print("files:", [(item["name"], item.get("size")) for item in files])


if __name__ == "__main__":
    main()
