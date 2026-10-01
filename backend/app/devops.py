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
import re
from dataclasses import dataclass
from urllib.parse import quote

import httpx

from app.models import (
    CreatedStory,
    FieldChange,
    StoryDraftContent,
    StoryTarget,
    WorkItemChange,
    WorkItemDetail,
    WorkItemSummary,
)

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


class DevOpsConflict(RuntimeError):
    """The story changed since SIP read it (the /rev test failed). Nothing was overwritten."""


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


def _story_language(content: StoryDraftContent, fallback: str) -> str:
    """The language the story is written in wins over the conversation's interface language."""
    return content.language or fallback


def description(content: StoryDraftContent, language: str) -> str:
    sentence, _ = STORY_SENTENCE.get(_story_language(content, language), STORY_SENTENCE["en"])
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


def _description_html(sentence: str, reason: str, language: str) -> str:
    _, reason_label = STORY_SENTENCE.get(language, STORY_SENTENCE["en"])
    body = f"<p>{html.escape(sentence)}</p>"
    if reason:
        body += f"<p><strong>{reason_label}:</strong> {html.escape(reason)}</p>"
    return body


def list_tags() -> list[str]:
    """The tags that already exist in the project. New tags may not be created (TF401289)."""
    settings = _settings()
    try:
        with client_factory(settings) as http:
            response = http.get(
                f"{settings.base}/{quote(settings.project)}/_apis/wit/tags",
                params={"api-version": "7.1-preview.1"},
            )
    except httpx.HTTPError as exc:
        raise DevOpsUnavailable("Azure DevOps could not be reached.") from exc
    _check_auth(response)
    if response.status_code >= 400:
        raise DevOpsUnavailable(f"Azure DevOps did not return the tags: {_devops_message(response)}")
    return sorted((item["name"] for item in response.json().get("value", [])), key=str.casefold)


def resolve_tags(names: list[str], existing: list[str]) -> list[str]:
    """Existing tags in their real spelling; refuses any tag that does not exist yet."""
    known = {tag.casefold(): tag for tag in existing}
    unknown = [name for name in names if name.casefold() not in known]
    if unknown:
        raise ValueError(
            f"Tag {', '.join(unknown)} does not exist in Azure DevOps, and new tags may not be created. "
            "Choose an existing tag."
        )
    return [known[name.casefold()] for name in names]


def _tags_value(tags: list[str]) -> str:
    return "; ".join(tags)


def story_patch(
    content: StoryDraftContent, language: str, iteration_path: str, assigned_to: str | None = None
) -> list[dict]:
    """The JSON Patch document for a new User Story. All text is escaped: DevOps stores HTML."""
    body = _description_html(
        description(content, language), content.estimation_reason, _story_language(content, language)
    )
    fields = {
        "System.Title": content.title,
        "System.Description": body,
        "Custom.EntryCriteria": _list_html(content.entry_criteria),
        "Microsoft.VSTS.Common.AcceptanceCriteria": _list_html(content.acceptance_criteria),
        "Microsoft.VSTS.Scheduling.StoryPoints": content.story_points,
        # Without an iteration path the story lands on the project root, which is
        # the backlog; a sprint path puts it on that sprint's board.
        "System.IterationPath": iteration_path,
        # A resolved account (uniqueName), never a guessed name.
        "System.AssignedTo": assigned_to,
        # Only existing tags, already checked by SIP.
        "System.Tags": _tags_value(content.tags),
    }
    return [
        {"op": "add", "path": f"/fields/{name}", "value": value}
        for name, value in fields.items()
        if value not in ("", None)
    ]


def create_story(
    content: StoryDraftContent, language: str, iteration_path: str, assigned_to: str | None = None
) -> CreatedStory:
    """Create the story once. Never retried here: a lost answer does not mean a lost story."""
    settings = _settings()
    url = f"{settings.base}/{quote(settings.project)}/_apis/wit/workitems/$User%20Story"
    try:
        with client_factory(settings) as http:
            response = http.post(
                url,
                params={"api-version": API_VERSION},
                headers={"Content-Type": "application/json-patch+json"},
                json=story_patch(content, language, iteration_path, assigned_to),
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


# --- Reading and changing existing stories (skill routes A, C and E) ----------

LIST_FIELDS = (
    "System.Id,System.Title,System.WorkItemType,System.State,System.AssignedTo,"
    "System.IterationPath,Microsoft.VSTS.Scheduling.StoryPoints"
)
DETAIL_FIELDS = LIST_FIELDS + (
    ",System.Rev,System.Tags,System.Description,Custom.EntryCriteria,Microsoft.VSTS.Common.AcceptanceCriteria"
)
MAX_LIST = 200  # Azure DevOps returns at most 200 work items per batch
# Statuses in the order the board shows them.
STATE_ORDER = ("New", "Refinement", "To Be Planned", "Ready", "Active", "Resolved", "Closed", "Removed")
BOARD_TYPES = "[System.WorkItemType] IN ('User Story', 'Bug') AND [System.State] <> 'Removed'"


def team_members() -> list[tuple[str, str]]:
    """(display name, account) of the team; the account never goes to the model."""
    settings = _settings()
    try:
        with client_factory(settings) as http:
            response = http.get(
                f"{settings.base}/_apis/projects/{quote(settings.project)}/teams/{quote(settings.team)}/members",
                params={"api-version": API_VERSION, "$top": "200"},
            )
    except httpx.HTTPError as exc:
        raise DevOpsUnavailable("Azure DevOps could not be reached.") from exc
    _check_auth(response)
    if response.status_code >= 400:
        raise DevOpsUnavailable(f"Azure DevOps did not return the team: {_devops_message(response)}")
    members = [item.get("identity", {}) for item in response.json().get("value", [])]
    return sorted(
        ((member["displayName"], member["uniqueName"]) for member in members if member.get("uniqueName")),
        key=lambda member: member[0].casefold(),
    )


def resolve_person(name: str, members: list[tuple[str, str]]) -> tuple[str, str]:
    """A team member by (part of) their display name; refuses to guess between several."""
    wanted = " ".join(name.split()).casefold()
    exact = [member for member in members if member[0].casefold() == wanted]
    if exact:
        return exact[0]
    partial = [member for member in members if wanted and wanted in member[0].casefold()]
    if len(partial) == 1:
        return partial[0]
    if not partial:
        raise ValueError(f"'{name}' is not a member of the team in Azure DevOps.")
    raise ValueError(f"'{name}' matches several team members: {', '.join(member[0] for member in partial)}.")


def person_for_email(email: str, members: list[tuple[str, str]]) -> tuple[str, str] | None:
    return next((member for member in members if member[1].casefold() == email.casefold()), None)


def _wiql_text(value: str) -> str:
    return value.replace("'", "''")


def _summary(item: dict, settings: Settings) -> WorkItemSummary:
    fields = item.get("fields", {})
    assigned = fields.get("System.AssignedTo")
    return WorkItemSummary(
        id=item["id"],
        title=fields.get("System.Title", ""),
        work_item_type=fields.get("System.WorkItemType", ""),
        state=fields.get("System.State", ""),
        story_points=fields.get("Microsoft.VSTS.Scheduling.StoryPoints"),
        assigned_to=assigned.get("displayName") if isinstance(assigned, dict) else assigned,
        iteration_path=fields.get("System.IterationPath", ""),
        url=settings.work_item_url(item["id"]),
    )


def _query(where: str) -> list[WorkItemSummary]:
    settings = _settings()
    query = f"SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = @project AND {where} ORDER BY [System.Id]"
    try:
        with client_factory(settings) as http:
            response = http.post(
                f"{settings.base}/{quote(settings.project)}/_apis/wit/wiql",
                params={"api-version": API_VERSION, "$top": str(MAX_LIST)},
                json={"query": query},
            )
            _check_auth(response)
            if response.status_code >= 400:
                raise DevOpsUnavailable(f"Azure DevOps could not be searched: {_devops_message(response)}")
            ids = [int(row["id"]) for row in response.json().get("workItems", [])][:MAX_LIST]
            if not ids:
                return []
            details = http.get(
                f"{settings.base}/{quote(settings.project)}/_apis/wit/workitems",
                params={"ids": ",".join(map(str, ids)), "fields": LIST_FIELDS, "api-version": API_VERSION},
            )
            _check_auth(details)
            details.raise_for_status()
    except httpx.HTTPError as exc:
        raise DevOpsUnavailable("Azure DevOps could not be reached.") from exc
    items = [_summary(item, settings) for item in details.json().get("value", [])]
    rank = {state: index for index, state in enumerate(STATE_ORDER)}
    return sorted(items, key=lambda item: (rank.get(item.state, len(rank)), item.id))


def sprint_items(iteration_path: str) -> list[WorkItemSummary]:
    return _query(f"[System.IterationPath] = '{_wiql_text(iteration_path)}' AND {BOARD_TYPES}")


def assigned_items(account: str, iteration_path: str | None = None) -> list[WorkItemSummary]:
    where = f"[System.AssignedTo] = '{_wiql_text(account)}' AND [System.State] NOT IN ('Closed', 'Removed')"
    if iteration_path:
        where += f" AND [System.IterationPath] = '{_wiql_text(iteration_path)}'"
    return _query(where)


def get_item(item_id: int) -> WorkItemDetail:
    settings = _settings()
    try:
        with client_factory(settings) as http:
            response = http.get(
                f"{settings.base}/{quote(settings.project)}/_apis/wit/workitems/{int(item_id)}",
                params={"fields": DETAIL_FIELDS, "api-version": API_VERSION},
            )
    except httpx.HTTPError as exc:
        raise DevOpsUnavailable("Azure DevOps could not be reached.") from exc
    _check_auth(response)
    if response.status_code == 404:
        raise ValueError(f"Work item {item_id} does not exist in project {settings.project}.")
    if response.status_code >= 400:
        raise DevOpsUnavailable(f"Azure DevOps did not return work item {item_id}: {_devops_message(response)}")
    item = response.json()
    fields = item.get("fields", {})
    summary = _summary(item, settings)
    return WorkItemDetail(
        **summary.model_dump(),
        rev=fields.get("System.Rev", item.get("rev", 0)),
        tags=[tag.strip() for tag in (fields.get("System.Tags") or "").split(";") if tag.strip()],
        description=plain_text(fields.get("System.Description", "")),
        entry_criteria=plain_text(fields.get("Custom.EntryCriteria", "")),
        acceptance_criteria=plain_text(fields.get("Microsoft.VSTS.Common.AcceptanceCriteria", "")),
    )


def plain_text(value: str | None) -> str:
    """Readable text from DevOps HTML: list items on their own line, tags removed."""
    if not value:
        return ""
    text = re.sub(r"(?i)<\s*(br|/p|/div|/li)\s*/?>", "\n", value)
    text = re.sub(r"(?i)<li[^>]*>", "- ", text)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def _same(a: str, b: str) -> bool:
    return " ".join(plain_text(a).split()) == " ".join(plain_text(b).split())


def plan_change(
    change: WorkItemChange,
    current: WorkItemDetail,
    language: str,
    targets: list[StoryTarget],
    members: list[tuple[str, str]],
    existing_tags: list[str] | None = None,
) -> tuple[list[dict], list[FieldChange]]:
    """The JSON Patch operations and the before/after list for a proposed change.

    Only fields that really change are included. Raises ValueError for anything
    SIP will not do (a person outside the team, a closed sprint, half a
    description).
    """
    ops: list[dict] = []
    shown: list[FieldChange] = []
    story_language = change.language or language

    def add(path: str, value, field: str, before: str, after: str) -> None:
        ops.append({"op": "add", "path": f"/fields/{path}", "value": value})
        shown.append(FieldChange(field=field, before=before, after=after))

    if change.title and change.title != current.title:
        add("System.Title", change.title, "title", current.title, change.title)
    parts = (change.role, change.capability, change.value)
    if any(parts):
        if not all(parts):
            raise ValueError("A new description needs role, capability and value together.")
        content = StoryDraftContent(role=change.role, capability=change.capability, value=change.value, language=story_language)
        body = _description_html(description(content, language), change.estimation_reason or "", story_language)
        if not _same(body, current.description):
            add("System.Description", body, "description", current.description, plain_text(body))
    for name, path, before in (
        ("entry_criteria", "Custom.EntryCriteria", current.entry_criteria),
        ("acceptance_criteria", "Microsoft.VSTS.Common.AcceptanceCriteria", current.acceptance_criteria),
    ):
        items = getattr(change, name)
        if items is not None:
            body = _list_html(items)
            if not _same(body, before):
                add(path, body, name, before, plain_text(body))
    if change.story_points is not None and change.story_points != current.story_points:
        before = "" if current.story_points is None else f"{current.story_points:g}"
        add("Microsoft.VSTS.Scheduling.StoryPoints", change.story_points, "story_points", before, str(change.story_points))
    if change.state and change.state != current.state:
        if current.state in ("Closed", "Removed"):
            raise ValueError(f"Work item {current.id} is {current.state}; SIP does not reopen it.")
        add("System.State", change.state, "state", current.state, change.state)
    if change.target_kind:
        path = resolve_iteration(
            StoryDraftContent(target_kind=change.target_kind, iteration_path=change.iteration_path), targets
        )
        if path != current.iteration_path:
            add("System.IterationPath", path, "iteration_path", current.iteration_path, path)
    if change.assigned_to:
        display, account = resolve_person(change.assigned_to, members)
        if display != (current.assigned_to or ""):
            add("System.AssignedTo", account, "assigned_to", current.assigned_to or "", display)
    if change.add_tags or change.remove_tags:
        added = resolve_tags(change.add_tags or [], existing_tags or [])
        removed = {tag.casefold() for tag in change.remove_tags or []}
        tags = [tag for tag in current.tags if tag.casefold() not in removed]
        tags += [tag for tag in added if tag.casefold() not in {t.casefold() for t in tags}]
        if [t.casefold() for t in tags] != [t.casefold() for t in current.tags]:
            add("System.Tags", _tags_value(tags), "tags", _tags_value(current.tags), _tags_value(tags))
    return ops, shown


def update_item(item_id: int, base_rev: int, ops: list[dict]) -> int:
    """Apply the operations only if the story is still at base_rev. Returns the new revision."""
    settings = _settings()
    try:
        with client_factory(settings) as http:
            response = http.patch(
                f"{settings.base}/{quote(settings.project)}/_apis/wit/workitems/{int(item_id)}",
                params={"api-version": API_VERSION},
                headers={"Content-Type": "application/json-patch+json"},
                json=[{"op": "test", "path": "/rev", "value": base_rev}, *ops],
            )
    except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
        raise DevOpsRejected("Azure DevOps could not be reached. Nothing was changed.") from exc
    except httpx.HTTPError as exc:
        raise DevOpsUncertain("Azure DevOps did not answer in time.") from exc
    _check_auth(response)
    message = _devops_message(response)
    if response.status_code in (409, 412) or "TF26071" in message:
        raise DevOpsConflict("Someone changed this story in the meantime. Nothing was overwritten.")
    if response.status_code >= 500:
        raise DevOpsUncertain(f"Azure DevOps answered with an error ({response.status_code}).")
    if response.status_code >= 400:
        raise DevOpsRejected(f"Azure DevOps refused the change: {message}")
    try:
        body = response.json()
        return int(body.get("rev") or body["fields"]["System.Rev"])
    except (ValueError, KeyError, TypeError) as exc:
        raise DevOpsUncertain("Azure DevOps answered without a revision.") from exc


def change_applied(ops: list[dict], current: WorkItemDetail, members: list[tuple[str, str]]) -> bool:
    """Whether the story already holds every value of the change (used after an uncertain write)."""
    accounts = {account.casefold(): display for display, account in members}
    for op in ops:
        field = op["path"].removeprefix("/fields/")
        value = op["value"]
        checks = {
            "System.Title": lambda: current.title == value,
            "System.State": lambda: current.state == value,
            "System.IterationPath": lambda: current.iteration_path == value,
            "Microsoft.VSTS.Scheduling.StoryPoints": lambda: current.story_points == value,
            "System.AssignedTo": lambda: accounts.get(str(value).casefold()) == current.assigned_to,
            "System.Tags": lambda: {t.strip().casefold() for t in str(value).split(";") if t.strip()}
            == {t.casefold() for t in current.tags},
            "System.Description": lambda: _same(value, current.description),
            "Custom.EntryCriteria": lambda: _same(value, current.entry_criteria),
            "Microsoft.VSTS.Common.AcceptanceCriteria": lambda: _same(value, current.acceptance_criteria),
        }
        if not checks.get(field, lambda: False)():
            return False
    return True
