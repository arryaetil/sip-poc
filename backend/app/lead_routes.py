"""Lead finder endpoints: the intake chat, the lists, the scorecard and the export.

Roles: admin and sales only (`_role_allows` in main.py). Every list is visible to
both roles; deleting is for the creator or an admin. Lists expire after
RETENTION_DAYS and a housekeeping thread deletes them (see `start_housekeeping`).
"""

from __future__ import annotations

from datetime import date
import hashlib
import json
from types import SimpleNamespace
import logging
import re
import threading
import time
import traceback
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.assistants import _context_text
from app.knowledge import create_website_offering_profile, get_knowledge_document, load_knowledge_documents
from app.lead_search import LeadSearch, Serper, serper_key
from app.leads import (
    MAX_LEADS,
    MIN_USER_TURNS,
    RETENTION_DAYS,
    LeadBrief,
    LeadRow,
    LeadScore,
    ScoreCriterion,
    brief_complete,
    clean_brief,
    export_xlsx,
    score_row,
)
from app.models import ConversationMessage, ConversationSummary, StoredBusinessContext

logger = logging.getLogger("sip.leads")
router = APIRouter(prefix="/api/leads")
HOUSEKEEPING_SECONDS = 6 * 60 * 60
# Spending guard: one search at a time per user, and a daily number of searches.
DAILY_LEAD_SEARCHES = 10
LEAD_READY_REASON = "Lead search brief confirmed."


def _main():
    # main.py imports this module; reach its helpers at call time.
    from app import main

    return main


class LeadSettings(BaseModel):
    available: bool
    missing: Literal["search", "assistant"] | None
    max_leads: int
    retention_days: int


class LeadSource(BaseModel):
    """A service or solution from the reviewed ETIL / ibc group website pages."""

    id: str
    name: str
    organisation: str
    offering_type: str


class LeadChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4_000)
    conversation_id: str | None = None
    context_id: str | None = None
    language: Literal["en", "nl", "de"] = "nl"
    scoring: Literal["levels", "sam_points"] | None = None


class LeadChatResponse(BaseModel):
    conversation_id: str
    message: ConversationMessage
    brief: LeadBrief
    ready: bool
    context_id: str | None
    context_name: str | None


class LeadConversation(BaseModel):
    ready: bool = False
    conversation: ConversationSummary
    messages: list[ConversationMessage]
    brief: LeadBrief | None
    context_id: str | None
    context_name: str | None


class CreateLeadListRequest(BaseModel):
    context_id: str
    conversation_id: str | None = None
    brief: LeadBrief
    language: Literal["en", "nl", "de"] = "nl"


class ScorecardRequest(BaseModel):
    scorecard: list[ScoreCriterion]


class LeadRowOut(LeadRow):
    score: LeadScore


class LeadListSummary(BaseModel):
    id: str
    title: str
    context_id: str
    context_name: str
    status: Literal["running", "done", "failed", "interrupted"]
    error: str | None
    requested: int
    found: int
    mine: bool
    created_by: str | None
    skipped: int = 0  # email of the creator; None when unknown (local development)
    created_at: str
    expires_at: str


class LeadListDetail(LeadListSummary):
    brief: LeadBrief
    rows: list[LeadRowOut]
    counts: dict[str, int]


# --------------------------------------------------------------------------- helpers


WEB_PREFIX = "web:"
WEB_TEXT_LIMIT = 6_000


def _approved_context(context_id: str, owner_id: str, is_admin: bool) -> SimpleNamespace:
    """What a lead search starts from: an approved Business Context, or a service or
    solution page from the reviewed website corpus (id "web:<source id>")."""
    if context_id.startswith(WEB_PREFIX):
        document = get_knowledge_document(context_id.removeprefix(WEB_PREFIX))
        profile = create_website_offering_profile(document) if document else None
        if profile is None or not profile.offering_type:
            raise HTTPException(status_code=404, detail="Website service or solution not found")
        name = profile.name or document.title
        text = (
            f"{name}: {profile.offering_type} of {document.organisation}, from its reviewed website page "
            f"({document.canonical_url}).\n\n{document.content[:WEB_TEXT_LIMIT]}"
        )
        return SimpleNamespace(id=context_id, name=name, text=text)
    context: StoredBusinessContext | None = _main().get_context_store().get(context_id, owner_id, is_admin)
    if context is None or context.status != "approved":
        raise HTTPException(status_code=404, detail="Approved Business Context not found")
    return SimpleNamespace(id=context.id, name=context.name, text=_context_text(context))


def _missing() -> Literal["search", "assistant"] | None:
    if not serper_key():
        return "search"
    try:
        return None if _main().get_assistant().lead_available() else "assistant"
    except RuntimeError:
        return "assistant"


def _creators() -> dict[str, str]:
    """Owner id -> email, for lists stored before created_by existed."""
    main = _main()
    known = {user.id: user.email for user in main.get_context_store().list_users()}
    for email in main._env_users():
        known.setdefault("env:" + hashlib.sha256(email.encode()).hexdigest()[:24], email)
    return known


def _summary(record: dict, owner_id: str, found: int, creators: dict[str, str] | None = None) -> dict:
    """A list row (sqlite) or a full record, as plain fields."""
    brief = record["brief"]
    brief = brief if isinstance(brief, LeadBrief) else LeadBrief.model_validate_json(brief)
    return {
        "id": record["id"],
        "title": brief.title,
        "context_id": record["context_id"],
        "context_name": record["context_name"],
        "status": record["status"],
        "error": record["error"],
        "requested": brief.count or 0,
        "found": found,
        "mine": record["owner_id"] == owner_id,
        "skipped": record.get("skipped") or 0,
        "created_by": record.get("created_by") or (creators or {}).get(record["owner_id"]),
        "created_at": record["created_at"],
        "expires_at": record["expires_at"],
    }


def _detail(record, owner_id: str) -> LeadListDetail:
    rows = [LeadRowOut(**row.model_dump(), score=score_row(row, record.brief.scorecard, record.brief.scoring)) for row in record.rows]
    counts = {level: sum(1 for row in rows if row.score.level == level) for level in ("high", "medium", "low")}
    summary = _summary(vars(record), owner_id, len(rows), None if record.created_by else _creators())
    return LeadListDetail(**summary, brief=record.brief, rows=rows, counts=counts)


def _owned_lead_conversation(conversation_id: str, owner_id: str):
    conversation = _main().get_context_store().get_conversation(conversation_id, owner_id)
    if conversation is None or conversation.kind != "lead":
        raise HTTPException(status_code=404, detail="Lead conversation not found")
    return conversation


def start_search(search: LeadSearch, list_id: str, owner_id: str, language: str, context_text: str) -> None:
    """The search takes minutes; the page polls the list while this thread fills it."""
    threading.Thread(
        target=search.run,
        args=(list_id, owner_id, language, context_text),
        name=f"lead-search-{list_id[:8]}",
        daemon=True,
    ).start()


# --------------------------------------------------------------------------- routes


@router.get("/settings", response_model=LeadSettings)
def lead_settings() -> LeadSettings:
    missing = _missing()
    return LeadSettings(available=missing is None, missing=missing, max_leads=MAX_LEADS, retention_days=RETENTION_DAYS)


@router.get("/sources", response_model=list[LeadSource])
def lead_sources() -> list[LeadSource]:
    """The services and solutions on the ETIL and ibc group websites, to search leads for."""
    sources = []
    for document in load_knowledge_documents():
        profile = create_website_offering_profile(document)
        if profile.offering_type:
            sources.append(LeadSource(
                id=f"{WEB_PREFIX}{document.source_id}",
                name=profile.name or document.title,
                organisation=document.organisation,
                offering_type=profile.offering_type,
            ))
    return sorted(sources, key=lambda item: (item.organisation, item.name.casefold()))


@router.post("/chat", response_model=LeadChatResponse)
def lead_chat(body: LeadChatRequest, request: Request) -> LeadChatResponse:
    """One intake turn. The brief the assistant proposes is cleaned and kept with the chat."""
    main = _main()
    owner_id, is_admin = main._actor(request)
    store = main.get_context_store()
    context = None
    if body.conversation_id:
        conversation = _owned_lead_conversation(body.conversation_id, owner_id)
        if conversation.portfolio_context_id:
            try:
                context = _approved_context(conversation.portfolio_context_id, owner_id, is_admin)
            except HTTPException:
                pass  # The conversation stays usable after a source is withdrawn.
    else:
        if body.context_id:
            context = _approved_context(body.context_id, owner_id, is_admin)
        conversation = store.create_conversation(owner_id, body.language, "lead")
    offerings = [
        {"id": item.id, "name": item.name, "summary": item.short_summary[:700]}
        for item in store.list(owner_id, is_admin, approved_only=True)
    ]
    for document in load_knowledge_documents():
        profile = create_website_offering_profile(document)
        if profile.offering_type:
            offerings.append({"id": WEB_PREFIX + document.source_id,
                              "name": profile.name or document.title,
                              "organisation": document.organisation,
                              "summary": document.content[:700]})
    context_text = json.dumps({
        "selected_offering": {"id": context.id, "name": context.name, "facts": context.text} if context else None,
        "available_offerings": offerings,
    }, ensure_ascii=False)
    current = store.lead_brief(conversation.id)
    try:
        turn = _main().get_assistant().lead_intake_turn(
            conversation.messages,
            body.message,
            body.language,
            owner_id,
            context_text,
            current.model_dump_json() if current else "",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        logger.error("Lead finder returned invalid output:\n%s", traceback.format_exc())
        raise HTTPException(status_code=502, detail="The Lead finder gave an answer SIP could not read. Please try again.") from exc
    except Exception as exc:
        logger.error("Lead finder request failed:\n%s", traceback.format_exc())
        raise HTTPException(status_code=502, detail="The Lead finder could not be reached. Please try again.") from exc
    selected_id = turn.context_id or (context.id if context else None)
    supported = turn.can_search
    if selected_id:
        if selected_id not in {item["id"] for item in offerings}:
            context = None
            supported = False
            turn.message = {"nl": "Ik vind hiervoor geen passende beschikbare dienst. Welke dienst of welk product bedoel je?",
                            "de": "Ich finde dafür kein verfügbares Angebot. Welchen Service oder welches Produkt meinst du?",
                            "en": "I cannot find a matching available offering. Which service or product do you mean?"}[body.language]
        else:
            context = _approved_context(selected_id, owner_id, is_admin)
            store.link_conversation_to_context(conversation.id, context.id, owner_id)
    proposed = turn.brief
    # Legacy API clients may still explicitly choose a mode; chat clients do not.
    if body.scoring is not None:
        proposed = proposed.model_copy(update={"scoring": body.scoring})
    brief = clean_brief(proposed)
    if brief.scoring == "levels" and (len(brief.scorecard) != len(proposed.scorecard)
                                        or len(brief.extra_columns) != len(proposed.extra_columns)):
        supported = False
        turn.message = {"nl": "Deze scorekaart kan ik niet volledig uitvoeren. Ik kan maximaal vier criteria op land, plaats of drie extra gegevens beoordelen. Hoe wil je de beoordeling vereenvoudigen?",
                        "de": "Diese Bewertung kann ich nicht vollständig ausführen. Möglich sind vier Kriterien zu Land, Ort oder drei zusätzlichen Angaben. Wie möchtest du sie vereinfachen?",
                        "en": "I cannot fully apply this scorecard. I can assess up to four criteria using country, city or three extra facts. How would you like to simplify it?"}[body.language]
    ready = bool(context) and supported and turn.ready and brief_complete(brief) and (
        sum(1 for message in conversation.messages if message.role == "user") + 1 >= MIN_USER_TURNS)
    updated = store.add_conversation_turn(
        conversation_id=conversation.id,
        user_message=body.message,
        assistant_message=turn.message,
        is_ready_to_save=False,
        readiness_reason=LEAD_READY_REASON if ready else "Lead search brief needs clarification or confirmation.",
        owner_id=owner_id,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Lead conversation not found")
    store.save_lead_brief(conversation.id, brief)
    return LeadChatResponse(
        conversation_id=conversation.id,
        message=updated.messages[-1],
        brief=brief,
        ready=ready,
        context_id=context.id if context else None,
        context_name=context.name if context else None,
    )


@router.get("/conversations", response_model=list[ConversationSummary])
def lead_conversations(request: Request) -> list[ConversationSummary]:
    main = _main()
    owner_id, _ = main._actor(request)
    # Intake chats are personal, also for an admin; the lists they produce are shared.
    return main.get_context_store().list_conversations(owner_id, False, "lead")


@router.get("/conversations/{conversation_id}", response_model=LeadConversation)
def lead_conversation(conversation_id: str, request: Request) -> LeadConversation:
    main = _main()
    owner_id, is_admin = main._actor(request)
    conversation = _owned_lead_conversation(conversation_id, owner_id)
    try:
        context = _approved_context(conversation.portfolio_context_id or "", owner_id, is_admin)
    except HTTPException:
        context = None  # deleted or no longer approved; the chat can still be read
    return LeadConversation(
        ready=bool(context) and conversation.readiness_reason == LEAD_READY_REASON,
        conversation=ConversationSummary(**conversation.model_dump(exclude={"messages"})),
        messages=conversation.messages,
        brief=main.get_context_store().lead_brief(conversation.id),
        context_id=context.id if context else None,
        context_name=context.name if context else None,
    )


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_lead_conversation(conversation_id: str, request: Request) -> Response:
    main = _main()
    owner_id, _ = main._actor(request)
    _owned_lead_conversation(conversation_id, owner_id)
    main.get_context_store().delete_conversation(conversation_id, owner_id)
    return Response(status_code=204)


@router.post("/lists", response_model=LeadListDetail, status_code=201)
def create_lead_list(body: CreateLeadListRequest, request: Request) -> LeadListDetail:
    """Store the brief and start the search in the background. The maximum is enforced here."""
    main = _main()
    owner_id, is_admin = main._actor(request)
    store = main.get_context_store()
    missing = _missing()
    if missing == "search":
        raise HTTPException(status_code=503, detail="Web search is not configured (SERPER_API_KEY).")
    if missing == "assistant":
        raise HTTPException(status_code=503, detail="The Lead finder assistant is not available yet.")
    context = _approved_context(body.context_id, owner_id, is_admin)
    if body.conversation_id:
        conversation = _owned_lead_conversation(body.conversation_id, owner_id)
        if conversation.readiness_reason != LEAD_READY_REASON or conversation.portfolio_context_id != context.id:
            raise HTTPException(status_code=422, detail="Confirm a supported search brief in the chat first")
        agreed = store.lead_brief(conversation.id)
        if agreed is None or clean_brief(body.brief) != agreed:
            raise HTTPException(status_code=422, detail="The search brief has changed; confirm it in the chat first")
    running, recent = store.lead_lists_by(owner_id)
    if running:
        raise HTTPException(status_code=429, detail="Your previous lead search is still running. Wait until it has finished.")
    if recent >= DAILY_LEAD_SEARCHES:
        raise HTTPException(status_code=429, detail="You have reached today's limit of lead searches. Try again tomorrow.")
    brief = clean_brief(body.brief)
    if brief.count is None:
        raise HTTPException(status_code=422, detail="Say how many leads you want first")
    if not brief_complete(brief):
        raise HTTPException(status_code=422, detail="The search brief is not complete yet; finish the conversation first")
    list_id = store.create_lead_list(
        owner_id, body.conversation_id, context.id, context.name, brief, body.language,
        created_by=getattr(request.state, "user_email", None),
    )
    search = LeadSearch(store, main.get_assistant(), Serper(serper_key()))
    start_search(search, list_id, owner_id, body.language, context.text)
    logger.info("lead_list_started list=%s count=%s", list_id, brief.count)
    return _detail(store.get_lead_list(list_id), owner_id)


@router.get("/lists", response_model=list[LeadListSummary])
def lead_lists(request: Request) -> list[LeadListSummary]:
    main = _main()
    owner_id, _ = main._actor(request)
    rows = main.get_context_store().list_lead_lists()
    creators = _creators() if any(not row["created_by"] for row in rows) else {}
    return [LeadListSummary(**_summary(dict(row), owner_id, row["found"], creators)) for row in rows]


@router.get("/lists/{list_id}", response_model=LeadListDetail)
def lead_list(list_id: str, request: Request) -> LeadListDetail:
    main = _main()
    owner_id, _ = main._actor(request)
    record = main.get_context_store().get_lead_list(list_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Lead list not found")
    return _detail(record, owner_id)


@router.put("/lists/{list_id}/scorecard", response_model=LeadListDetail)
def update_scorecard(list_id: str, body: ScorecardRequest, request: Request) -> LeadListDetail:
    """Change the scorecard; scores are recalculated from the stored facts, no new search."""
    main = _main()
    owner_id, is_admin = main._actor(request)
    store = main.get_context_store()
    record = store.get_lead_list(list_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Lead list not found")
    if record.owner_id != owner_id and not is_admin:
        raise HTTPException(status_code=403, detail="Only the creator of a lead list or an admin can change its scorecard.")
    brief = clean_brief(record.brief.model_copy(update={"scorecard": body.scorecard}))
    store.update_lead_brief(list_id, brief)
    return _detail(store.get_lead_list(list_id), owner_id)


@router.get("/lists/{list_id}/export")
def export_lead_list(list_id: str, language: Literal["en", "nl", "de"] = Query("nl")) -> Response:
    record = _main().get_context_store().get_lead_list(list_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Lead list not found")
    content = export_xlsx(
        record.brief,
        record.rows,
        context_name=record.context_name,
        created_at=record.created_at,
        expires_at=record.expires_at,
        language=language,
    )
    slug = re.sub(r"[^a-z0-9]+", "-", record.brief.title.casefold()).strip("-")[:60] or "leads"
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="leads-{slug}-{date.today().isoformat()}.xlsx"'},
    )


@router.delete("/lists/{list_id}", status_code=204)
def delete_lead_list(list_id: str, request: Request) -> Response:
    main = _main()
    owner_id, is_admin = main._actor(request)
    if not main.get_context_store().delete_lead_list(list_id, owner_id, is_admin):
        raise HTTPException(status_code=404, detail="Lead list not found")
    return Response(status_code=204)


# --------------------------------------------------------------------------- housekeeping


def purge_once(store) -> None:
    deleted = store.purge_expired_leads()
    if deleted:
        logger.info("lead_purge deleted=%s ids=%s", len(deleted), ",".join(deleted))


def start_housekeeping() -> None:
    """At startup: settle lists a restart cut off, then delete expired lists every six hours."""
    store = _main().get_context_store()
    interrupted = store.interrupt_running_lead_lists()
    if interrupted:
        logger.warning("lead_lists_interrupted count=%s", interrupted)

    def loop() -> None:
        while True:
            try:
                purge_once(store)
            except Exception:  # noqa: BLE001 - keep the cleanup alive; the next round retries
                logger.exception("lead_purge failed")
            time.sleep(HOUSEKEEPING_SECONDS)

    threading.Thread(target=loop, name="lead-housekeeping", daemon=True).start()
