"""Marketing studio: hand a conversation over to Open Design.

Open Design runs as its own Railway service behind a gateway
(marketing/open-design/gateway.mjs). SIP talks to it in two ways:

- server to server, over Railway's private network, with the daemon token, to
  create a project that already holds the brief, the house style and the
  sources the knowledge assistant used;
- by giving the signed-in user a short-lived signed link, which the gateway
  exchanges for its own session cookie. Users never see the daemon token.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from uuid import uuid4

import httpx

from app.models import ConversationMessage, KnowledgeChatSource, MarketingRequest

LINK_SECONDS = 120
BRANDS = {"etil": "user:etil", "ibc-group": "user:ibc-group"}

FORMAT_BRIEFS = {
    "linkedin_post": (
        "a LinkedIn post: one portrait 4:5 image (1080x1350) following the Etil LinkedIn post "
        "pattern in the design system, plus the post text (max 1,300 characters) as a separate note"
    ),
    "one_pager": "an A4 one-pager, ready to export as PDF",
    "presentation": "a presentation of about 6 to 10 slides, ready to export as PPTX",
}


class StudioUnavailable(RuntimeError):
    """The studio is not configured; endpoints answer 503."""


def _config() -> tuple[str, str, str, str]:
    internal = os.getenv("OPEN_DESIGN_INTERNAL_URL", "").strip().rstrip("/")
    public = os.getenv("OPEN_DESIGN_PUBLIC_URL", "").strip().rstrip("/")
    token = os.getenv("OPEN_DESIGN_TOKEN", "").strip()
    secret = os.getenv("STUDIO_HANDOFF_SECRET", "").strip()
    if not (internal and public and token and secret):
        raise StudioUnavailable("The marketing studio is not configured")
    return internal, public, token, secret


def signed_link(owner_id: str, next_path: str = "/") -> str:
    """A link the gateway accepts once, for LINK_SECONDS, for this user."""
    _, public, _, secret = _config()
    body = base64.urlsafe_b64encode(
        json.dumps({"sub": hashlib.sha256(owner_id.encode()).hexdigest()[:24], "exp": int(time.time()) + LINK_SECONDS, "next": next_path}).encode()
    ).rstrip(b"=").decode()
    signature = base64.urlsafe_b64encode(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    return f"{public}/__sip/enter?t={body}.{signature}"


def context_document(
    request: MarketingRequest,
    history: list[ConversationMessage],
    sources: list[KnowledgeChatSource],
) -> str:
    """What the designer may draw on: the brief, the conversation and the retrieved passages."""
    lines = [
        "# Context from SIP",
        "",
        "Use only the facts below. Do not invent customers, results, figures, quotes or capabilities.",
        "If something the brief needs is missing, leave a clearly marked placeholder instead.",
        "",
        "## Brief",
        request.brief,
        "",
    ]
    if sources:
        lines += ["## Sources used by the knowledge assistant", ""]
        for source in sources:
            lines.append(f"### {source.title}" + (f" ({source.url})" if source.url.startswith("http") else ""))
            lines += [f"> {passage}".replace("\n", "\n> ") for passage in source.passages] or ["(no passage returned)"]
            lines.append("")
    if history:
        lines += ["## Conversation in SIP", ""]
        for message in history[-12:]:
            lines.append(f"**{'User' if message.role == 'user' else 'Knowledge assistant'}:** {message.content}")
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def create_project(
    owner_id: str,
    request: MarketingRequest,
    history: list[ConversationMessage],
    sources: list[KnowledgeChatSource],
) -> str:
    """Create a ready-to-run Open Design project; returns the signed link to open it."""
    internal, _, token, _ = _config()
    project_id = f"sip-{uuid4().hex[:16]}"
    design_system = BRANDS.get(request.brand, BRANDS["etil"])
    headers = {"Authorization": f"Bearer {token}"}
    prompt = (
        f"Create {FORMAT_BRIEFS[request.format]}. Brief: {request.brief}\n\n"
        "Base every statement on context.md in this project. The official logos, example posts "
        "and approved images are in the brand/ folder of this project: use them. Load Ubuntu with "
        "@font-face from brand/fonts/Ubuntu-{Light,Regular,Medium,Bold}.ttf. Use only the official "
        "logo files in brand/, shown whole and never cropped, and never draw or create a logo."
    )
    with httpx.Client(base_url=internal, headers=headers, timeout=30) as http:
        created = http.post(
            "/api/projects",
            json={
                "id": project_id,
                "name": request.title or request.brief[:60],
                "designSystemId": design_system,
                "pendingPrompt": prompt,
                "customInstructions": (
                    "This project was started from SIP. context.md holds the only approved facts: "
                    "never invent customers, figures, results or capabilities. Follow the selected "
                    "design system strictly (colours, Ubuntu, logo rules, tone of voice). Write in the "
                    "language of the brief. For imagery, first use the approved images listed in the design "
                    "system (assets/images) or build the background with CSS; generate a new image only when "
                    "none fits, and then label it as AI-generated. Creative Commons images in the private "
                    "reference library require a fresh licence check and attribution before use."
                ),
                "skipDiscoveryBrief": True,
                "metadata": {"source": "sip", "format": request.format},
            },
        )
        if created.status_code >= 400:
            raise RuntimeError(f"Open Design refused the project: {created.status_code} {created.text[:200]}")
        uploaded = http.post(
            f"/api/projects/{project_id}/files",
            json={"name": "context.md", "content": context_document(request, history, sources), "encoding": "utf8"},
        )
        if uploaded.status_code >= 400:
            raise RuntimeError(f"Open Design refused the context file: {uploaded.status_code} {uploaded.text[:200]}")
        _copy_brand_assets(http, design_system, project_id)
    return signed_link(owner_id, f"/projects/{project_id}")


ASSET_TYPES = (".png", ".jpg", ".jpeg", ".svg", ".webp", ".ttf")


def _copy_brand_assets(http: httpx.Client, design_system: str, project_id: str) -> None:
    """Put the house style's logos, examples and images into the project's brand/ folder.

    The design system's prose reaches the model through the prompt, but its files
    do not: without copies in the project the model has no logo to place.
    """
    listing = http.get(f"/api/design-systems/{design_system}/files")
    listing.raise_for_status()
    for item in listing.json().get("files", []):
        path = item.get("path") or ""
        # The private source library remains available through the authenticated
        # design system, but copying hundreds of originals into every project
        # would waste storage and model context.
        if path.startswith("assets/private-library/"):
            continue
        if not path.startswith(("assets/", "fonts/")) or not path.lower().endswith(ASSET_TYPES):
            continue
        asset = http.get(f"/api/design-systems/{design_system}/static", params={"path": path})
        if asset.status_code >= 400:
            continue
        name = "brand/" + path.removeprefix("assets/")  # fonts/ keeps its folder: brand/fonts/
        http.post(
            f"/api/projects/{project_id}/files",
            data={"name": name},
            files={"file": (path.rsplit("/", 1)[-1], asset.content, asset.headers.get("content-type", "application/octet-stream"))},
        ).raise_for_status()
