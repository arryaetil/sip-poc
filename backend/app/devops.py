"""Azure DevOps for the Product Owner assistant: read sprints, create user stories.

One write exists: creating a User Story, and only from SIP's confirm endpoint
after the user approved that exact version. Nothing is updated, tagged,
commented, assigned or closed here; that matches the team's story rules (no
noise in ADO, Closed is the product owner's acceptance step).

Authentication is a Personal Access Token (AZURE_DEVOPS_PAT, Work Items read &
write) owned by one person: every story is created under that identity. That
is a conscious POC choice; SIP limits who may use it (SIP_PRODUCT_OWNER_WRITERS)
and production should move to a Microsoft Entra ID identity. The token never
leaves this module: it is not logged, not returned and not sent to a model.
"""

from __future__ import annotations

import base64
import html
import os
from dataclasses import dataclass
from urllib.parse import quote

import httpx

from app.models import CreatedStory, StoryDraftContent, StoryTarget

API_VERSION = "7.1"
TIMEOUT = httpx.Timeout(30.0, connect=10.0)

STORY_SENTENCE = {
    "nl": ("Als {role} wil ik {capability}, zodat {value}.", "Onderbouwing schatting"),
    "de": ("Als {role} möchte ich {capability}, damit {value}.", "Begründung der Schätzung"),
    "en": ("As {role} I want {capability}, so that {value}.", "Estimate rationale"),
}


class DevOpsUnavailable(RuntimeError):
    """Not configured, or the token was refused. Nothing was written."""


class DevOpsRejected(RuntimeError):
    """Azure DevOps answered and refused the story. Nothing was created."""


class DevOpsUncertain(RuntimeError):
    """The request may have reached Azure DevOps; the story may exist. Check before retrying."""


@dataclass(frozen=True)
class Settings:
    token: str
    organisation: str
    project: str
    team: str

    @property
    def base(self) -> str:
        return f"https://dev.azure.com/{quote(self.organisation)}"

    def work_item_url(self, item_id: int) -> str:
        return f"{self.base}/{quote(self.project)}/_workitems/edit/{item_id}"


def organisation() -> str:
    return os.getenv("AZURE_DEVOPS_ORG", "EtilSolutions").strip()


def project() -> str:
    return os.getenv("AZURE_DEVOPS_PROJECT", "Etil Solutions").strip()


def configured() -> bool:
    return bool(os.getenv("AZURE_DEVOPS_PAT", "").strip())


def _settings() -> Settings:
    token = os.getenv("AZURE_DEVOPS_PAT", "").strip()
    if not token:
        raise DevOpsUnavailable("Azure DevOps is not connected to SIP yet.")
    return Settings(token, organisation(), project(), os.getenv("AZURE_DEVOPS_TEAM", "Etil Solutions Team").strip())


def _client(settings: Settings) -> httpx.Client:
    basic = base64.b64encode(f":{settings.token}".encode()).decode()
    # No redirects: an expired token is answered with a sign-in redirect, not a 401.
    return httpx.Client(headers={"Authorization": f"Basic {basic}"}, timeout=TIMEOUT, follow_redirects=False)


# Tests replace this to talk to a fake Azure DevOps.
client_factory = _client


def _devops_message(response: httpx.Response) -> str:
    """Azure DevOps' own error text, without headers or anything sent."""
    try:
        message = response.json().get("message", "")
    except ValueError:
        message = ""
    return (message or response.reason_phrase or "")[:300]


def _check_auth(response: httpx.Response) -> None:
    if response.status_code in (401, 403) or 300 <= response.status_code < 400:
        raise DevOpsUnavailable(
            "Azure DevOps refused SIP's access token. It may have expired or lack Work Items rights."
        )


def list_targets() -> list[StoryTarget]:
    """Where a new story can go: the backlog, or a current or future sprint of the team."""
    settings = _settings()
    try:
        with client_factory(settings) as http:
            response = http.get(
                f"{settings.base}/{quote(settings.project)}/{quote(settings.team)}/_apis/work/teamsettings/iterations",
                params={"api-version": API_VERSION},
            )
    except httpx.HTTPError as exc:
        raise DevOpsUnavailable("Azure DevOps could not be reached.") from exc
    _check_auth(response)
    if response.status_code >= 400:
        raise DevOpsUnavailable(f"Azure DevOps did not return the sprints: {_devops_message(response)}")
    targets = [StoryTarget(kind="backlog", name="Backlog", iteration_path=settings.project)]
    for iteration in response.json().get("value", []):
        attributes = iteration.get("attributes") or {}
        timeframe = attributes.get("timeFrame", "")
        if timeframe not in ("current", "future"):
            continue  # past sprints are closed for new work
        targets.append(
            StoryTarget(
                kind="sprint",
                name=iteration.get("name", iteration["path"]),
                iteration_path=iteration["path"],
                timeframe=timeframe,
                start=(attributes.get("startDate") or "")[:10] or None,
                finish=(attributes.get("finishDate") or "")[:10] or None,
            )
        )
    return targets


def resolve_iteration(content: StoryDraftContent, targets: list[StoryTarget]) -> str:
    """The iteration path for the chosen target, checked against the live list."""
    if content.target_kind == "backlog":
        return next(target.iteration_path for target in targets if target.kind == "backlog")
    if content.target_kind == "sprint":
        for target in targets:
            if target.kind == "sprint" and target.iteration_path == content.iteration_path:
                return target.iteration_path
        raise ValueError("The chosen sprint is not an open sprint of the team. Choose the backlog or another sprint.")
    raise ValueError("Choose the backlog or a sprint first.")


def description(content: StoryDraftContent, language: str) -> str:
    sentence, _ = STORY_SENTENCE.get(language, STORY_SENTENCE["en"])
    if not (content.role and content.capability and content.value):
        return ""
    return sentence.format(
        role=content.role.rstrip(" ,."),
        capability=content.capability.rstrip(" ,."),
        value=content.value.rstrip(" ."),
    )


def _list_html(items: list[str]) -> str:
    rows = "".join(f"<li>{html.escape(item)}</li>" for item in items)
    return f"<ul>{rows}</ul>" if rows else ""


def story_patch(content: StoryDraftContent, language: str, iteration_path: str) -> list[dict]:
    """The JSON Patch document for a new User Story. All text is escaped: DevOps stores HTML."""
    _, reason_label = STORY_SENTENCE.get(language, STORY_SENTENCE["en"])
    body = f"<p>{html.escape(description(content, language))}</p>"
    if content.estimation_reason:
        body += f"<p><strong>{reason_label}:</strong> {html.escape(content.estimation_reason)}</p>"
    fields = {
        "System.Title": content.title,
        "System.Description": body,
        "Custom.EntryCriteria": _list_html(content.entry_criteria),
        "Microsoft.VSTS.Common.AcceptanceCriteria": _list_html(content.acceptance_criteria),
        "Microsoft.VSTS.Scheduling.StoryPoints": content.story_points,
        # Without an iteration path the story lands on the project root, which is
        # the backlog; a sprint path puts it on that sprint's board.
        "System.IterationPath": iteration_path,
    }
    return [
        {"op": "add", "path": f"/fields/{name}", "value": value}
        for name, value in fields.items()
        if value not in ("", None)
    ]


def create_story(content: StoryDraftContent, language: str, iteration_path: str) -> CreatedStory:
    """Create the story once. Never retried here: a lost answer does not mean a lost story."""
    settings = _settings()
    url = f"{settings.base}/{quote(settings.project)}/_apis/wit/workitems/$User%20Story"
    try:
        with client_factory(settings) as http:
            response = http.post(
                url,
                params={"api-version": API_VERSION},
                headers={"Content-Type": "application/json-patch+json"},
                json=story_patch(content, language, iteration_path),
            )
    except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
        # The connection never opened, so the request never arrived.
        raise DevOpsRejected("Azure DevOps could not be reached. Nothing was created.") from exc
    except httpx.HTTPError as exc:
        # Sent, but the answer was lost (timeout, dropped connection).
        raise DevOpsUncertain("Azure DevOps did not answer in time.") from exc
    _check_auth(response)
    if response.status_code >= 500:
        raise DevOpsUncertain(f"Azure DevOps answered with an error ({response.status_code}).")
    if response.status_code >= 400:
        raise DevOpsRejected(f"Azure DevOps refused the story: {_devops_message(response)}")
    try:
        item = response.json()
        item_id = int(item["id"])
    except (ValueError, KeyError, TypeError) as exc:
        raise DevOpsUncertain("Azure DevOps answered without a work item number.") from exc
    fields = item.get("fields", {})
    return CreatedStory(
        id=item_id,
        url=item.get("_links", {}).get("html", {}).get("href") or settings.work_item_url(item_id),
        title=fields.get("System.Title", content.title),
        iteration_path=fields.get("System.IterationPath", iteration_path),
    )


def find_created(title: str, since_utc: str) -> list[CreatedStory]:
    """User stories with this title created by SIP's identity since the confirmation.

    Used after an uncertain outcome. `since_utc` is SQLite's 'YYYY-MM-DD HH:MM:SS'.
    """
    settings = _settings()
    since = since_utc.replace(" ", "T") + "Z"
    escaped = title.replace("'", "''")
    query = (
        "SELECT [System.Id] FROM WorkItems "
        "WHERE [System.TeamProject] = @project AND [System.WorkItemType] = 'User Story' "
        f"AND [System.Title] = '{escaped}' AND [System.CreatedBy] = @me "
        f"AND [System.CreatedDate] >= '{since}' ORDER BY [System.Id]"
    )
    try:
        with client_factory(settings) as http:
            response = http.post(
                f"{settings.base}/{quote(settings.project)}/_apis/wit/wiql",
                params={"api-version": API_VERSION, "timePrecision": "true"},
                json={"query": query},
            )
            _check_auth(response)
            if response.status_code >= 400:
                raise DevOpsUnavailable(f"Azure DevOps could not be searched: {_devops_message(response)}")
            ids = [int(row["id"]) for row in response.json().get("workItems", [])]
            if not ids:
                return []
            details = http.get(
                f"{settings.base}/{quote(settings.project)}/_apis/wit/workitems",
                params={
                    "ids": ",".join(map(str, ids[:20])),
                    "fields": "System.Title,System.IterationPath",
                    "api-version": API_VERSION,
                },
            )
            _check_auth(details)
            details.raise_for_status()
    except httpx.HTTPError as exc:
        raise DevOpsUnavailable("Azure DevOps could not be reached to check the story.") from exc
    return [
        CreatedStory(
            id=item["id"],
            url=settings.work_item_url(item["id"]),
            title=item.get("fields", {}).get("System.Title", title),
            iteration_path=item.get("fields", {}).get("System.IterationPath", ""),
        )
        for item in details.json().get("value", [])
    ]
