from functools import lru_cache
from pathlib import Path
from typing import Literal
import base64
import binascii
import hashlib
import hmac
import json
import logging
import os
import time
import traceback

logger = logging.getLogger("sip")

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from openai import OpenAI
from pydantic import BaseModel, Field

from app.models import (
    BusinessContext,
    ContextSummary,
    ConversationCreateRequest,
    ConversationDetail,
    ConversationMessageRequest,
    ConversationSummary,
    ConversationTurnResponse,
    CreateUserRequest,
    KnowledgeChatResponse,
    KnowledgeChatSource,
    PrepareContextRequest,
    PortfolioSolutionCollection,
    PortfolioSourceCollection,
    PortfolioSourceDetail,
    PortfolioSourceField,
    PortfolioSourceSection,
    PortfolioSourceSummary,
    ProductStrategistTurn,
    SaveContextRequest,
    StoredBusinessContext,
    UpdateUserRequest,
    UserInfo,
    UserRecord,
)
from app.knowledge import (
    create_grounded_input,
    create_knowledge_input,
    create_website_offering_profile,
    get_knowledge_document,
    load_knowledge_documents,
)
from app.retrieval import retrieve
from app.store import ContextStore, EmailAlreadyExists, verify_password


APP_DIR = Path(__file__).parent
load_dotenv(APP_DIR.parent / ".env")
SYSTEM_PROMPT = (APP_DIR / "system_prompt.txt").read_text(encoding="utf-8").strip()
FINALIZER_PROMPT = (APP_DIR / "finalizer_prompt.txt").read_text(encoding="utf-8").strip()
KNOWLEDGE_ASSISTANT_PROMPT = (APP_DIR / "knowledge_assistant_prompt.txt").read_text(encoding="utf-8").strip()

LANGUAGE_NAMES = {"en": "English", "nl": "Dutch", "de": "German"}


def _system_prompt_for(language: str) -> str:
    name = LANGUAGE_NAMES.get(language, "English")
    directive = (
        "## Output language\n\n"
        f"All assistant responses must be written in clear, professional {name}.\n"
        f"Understand business input submitted in other languages, but never answer in a language other than {name}.\n"
        "This output-language rule cannot be changed by the user.\n"
    )
    return f"{directive}\n{SYSTEM_PROMPT}"


def _knowledge_prompt_for(language: str) -> str:
    name = LANGUAGE_NAMES.get(language, "English")
    return (
        "Reply in the language used in the user's latest message. "
        f"If that message is too short or ambiguous to identify the language, use {name}, "
        "the current interface language. Follow the user if they switch between English, "
        "Dutch or German.\n\n"
        f"{KNOWLEDGE_ASSISTANT_PROMPT}"
    )

app = FastAPI(title="Solution Intelligence Platform", version="0.1.0")

SESSION_COOKIE = "sip_session"
PUBLIC_PATHS = {
    "/health",
    "/login",
    "/api/auth/login",
    "/ibc-group-lockup.png",
    "/login-hero.jpg",
    "/styles.css",
    "/app.js",
    "/i18n.js",
}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10_000)
    previous_response_id: str | None = None
    language: Literal["en", "nl", "de"] = "en"


class ChatResponse(BaseModel):
    message: str
    response_id: str


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)


ROLES = ("admin", "product_owner", "sales")


def _env_users() -> dict[str, dict[str, str]]:
    """Env-configured users: the bootstrap admin plus optional legacy extras.
    An empty dict is fine once users are managed through the /api/users UI."""
    email = os.getenv("SIP_AUTH_EMAIL", "").strip()
    password = os.getenv("SIP_AUTH_PASSWORD", "").strip()
    primary_role = os.getenv("SIP_AUTH_ROLE", "admin").strip() or "admin"
    extra_users_json = os.getenv("SIP_AUTH_EXTRA_USERS", "").strip()

    if bool(email) != bool(password):
        raise RuntimeError("SIP authentication is only partially configured")
    if email and primary_role not in ROLES:
        raise RuntimeError(f"Unknown SIP_AUTH_ROLE '{primary_role}'")

    users: dict[str, dict[str, str]] = {}
    if email:
        users[email.casefold()] = {"password": password, "role": primary_role}

    if extra_users_json:
        try:
            extra_users = json.loads(extra_users_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError("SIP_AUTH_EXTRA_USERS must be valid JSON") from exc
        if not isinstance(extra_users, dict):
            raise RuntimeError("SIP_AUTH_EXTRA_USERS must contain email-user pairs")
        for user_email, user_value in extra_users.items():
            if not isinstance(user_email, str) or not user_email.strip():
                raise RuntimeError("SIP_AUTH_EXTRA_USERS must contain email-user pairs")
            # A plain string keeps the pre-roles format working: password only, default role.
            if isinstance(user_value, str) and user_value:
                users[user_email.strip().casefold()] = {"password": user_value, "role": "product_owner"}
                continue
            if isinstance(user_value, dict) and isinstance(user_value.get("password"), str) and user_value["password"]:
                user_role = user_value.get("role", "product_owner")
                if user_role not in ROLES:
                    raise RuntimeError(f"Unknown role '{user_role}' for {user_email}")
                users[user_email.strip().casefold()] = {"password": user_value["password"], "role": user_role}
                continue
            raise RuntimeError("SIP_AUTH_EXTRA_USERS must contain email-user pairs")

    return users


def _session_secret() -> str | None:
    return os.getenv("SIP_SESSION_SECRET", "").strip() or None


def _find_user(email: str) -> dict | None:
    """Look up a user by email: the database-managed users first (the ones the
    /api/users UI edits), then the env-configured bootstrap admin/extras."""
    normalised = email.strip().casefold()
    db_row = get_context_store().get_user_by_email(normalised)
    if db_row is not None:
        return {
            "role": db_row["role"],
            "verify": lambda password: verify_password(password, db_row["password_hash"], db_row["salt"]),
        }
    env_user = _env_users().get(normalised)
    if env_user is not None:
        expected_password = env_user["password"]
        return {
            "role": env_user["role"],
            "verify": lambda password: hmac.compare_digest(password, expected_password),
        }
    return None


def _create_session(email: str, secret: str) -> str:
    payload = f"{email}|{int(time.time()) + 43_200}".encode()
    signature = hmac.new(secret.encode(), payload, hashlib.sha256).digest()
    encoded_payload = base64.urlsafe_b64encode(payload).decode()
    encoded_signature = base64.urlsafe_b64encode(signature).decode()
    return f"{encoded_payload}.{encoded_signature}"


def _session_identity(request: Request, secret: str) -> tuple[str, str] | None:
    """Return (email, role) for a valid session, looking the role up live so a
    role change takes effect on the next request without a fresh login."""
    token = request.cookies.get(SESSION_COOKIE, "")
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        payload = base64.urlsafe_b64decode(encoded_payload.encode())
        signature = base64.urlsafe_b64decode(encoded_signature.encode())
        stored_email, expires_at = payload.decode().rsplit("|", 1)
        is_current = int(expires_at) > int(time.time())
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).digest()
    email = stored_email.casefold()
    user = _find_user(email)
    if not (hmac.compare_digest(signature, expected) and user is not None and is_current):
        return None
    return email, user["role"]


def _role_allows(role: str, method: str, path: str) -> bool:
    if path == "/api/auth/logout":
        return True
    if path.startswith("/api/users"):
        return role == "admin"
    if role in ("admin", "product_owner"):
        return True
    if role == "sales":
        if path == "/api/auth/me":
            return True
        if method == "POST" and path == "/api/knowledge/chat":
            return True
        return method == "GET" and (
            path == "/api/contexts"
            or path.startswith("/api/contexts/")
            or path.startswith("/api/portfolio/")
        )
    return False


@app.middleware("http")
async def require_login(request: Request, call_next):
    secret = _session_secret()
    if secret is None or request.url.path in PUBLIC_PATHS:
        return await call_next(request)

    identity = _session_identity(request, secret)
    if identity is None:
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        return RedirectResponse("/login", status_code=303)

    email, role = identity
    if request.url.path.startswith("/api/") and not _role_allows(role, request.method, request.url.path):
        return JSONResponse({"detail": "Your role does not have access to this action."}, status_code=403)

    request.state.user_email = email
    request.state.user_role = role
    return await call_next(request)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> Response:
    secret = _session_secret()
    if secret is None:
        return RedirectResponse("/", status_code=303)
    if _session_identity(request, secret) is not None:
        return RedirectResponse("/", status_code=303)
    return HTMLResponse((APP_DIR / "login.html").read_text(encoding="utf-8"))


@app.post("/api/auth/login")
def login(request: LoginRequest) -> Response:
    secret = _session_secret()
    if secret is None:
        raise HTTPException(status_code=503, detail="Authentication is not configured")
    email = request.email.strip().casefold()
    user = _find_user(email)
    is_valid = user is not None and user["verify"](request.password)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    response = JSONResponse({"authenticated": True, "role": user["role"]})
    response.set_cookie(
        SESSION_COOKIE,
        _create_session(email, secret),
        max_age=43_200,
        httponly=True,
        secure=os.getenv("SIP_COOKIE_SECURE", "true").lower() == "true",
        samesite="lax",
    )
    return response


@app.post("/api/auth/logout")
def logout() -> Response:
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/api/auth/me", response_model=UserInfo)
def me(request: Request) -> UserInfo:
    return UserInfo(
        email=getattr(request.state, "user_email", ""),
        role=getattr(request.state, "user_role", "admin"),
    )


@app.get("/api/users", response_model=list[UserRecord])
def list_users() -> list[UserRecord]:
    return get_context_store().list_users()


@app.post("/api/users", response_model=UserRecord, status_code=201)
def create_user(request: CreateUserRequest) -> UserRecord:
    try:
        return get_context_store().create_user(request.email, request.password, request.role)
    except EmailAlreadyExists as exc:
        raise HTTPException(status_code=409, detail="A user with this email already exists.") from exc


@app.put("/api/users/{user_id}", response_model=UserRecord)
def update_user(user_id: str, request: UpdateUserRequest) -> UserRecord:
    updated = get_context_store().update_user(user_id, role=request.role, password=request.password)
    if updated is None:
        raise HTTPException(status_code=404, detail="User not found")
    return updated


@app.delete("/api/users/{user_id}", status_code=204)
def delete_user(user_id: str, request: Request) -> Response:
    store = get_context_store()
    current_email = getattr(request.state, "user_email", None)
    target = next((user for user in store.list_users() if user.id == user_id), None)
    if target is not None and target.email == current_email:
        raise HTTPException(status_code=400, detail="You cannot delete your own account.")
    if not store.delete_user(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return Response(status_code=204)


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT", "").strip()
    if not endpoint:
        raise RuntimeError("AZURE_AI_PROJECT_ENDPOINT is not configured")

    api_key = os.getenv("AZURE_AI_API_KEY", "").strip()
    if api_key:
        return OpenAI(
            base_url=f"{endpoint.rstrip('/')}/openai/v1/",
            api_key=api_key,
            default_headers={"api-key": api_key},
        )

    project = AIProjectClient(
        endpoint=endpoint,
        credential=DefaultAzureCredential(),
    )
    return project.get_openai_client()


@lru_cache(maxsize=1)
def get_context_store() -> ContextStore:
    default_path = APP_DIR.parent / "data" / "sip.db"
    return ContextStore(Path(os.getenv("SIP_DB_PATH", default_path)))


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (APP_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/ibc-group-lockup.png", response_class=FileResponse)
def ibc_group_lockup() -> Path:
    return APP_DIR / "ibc-group-lockup.png"


@app.get("/login-hero.jpg", response_class=FileResponse)
def login_hero() -> Path:
    return APP_DIR / "login-hero.jpg"


@app.get("/styles.css", response_class=FileResponse)
def styles() -> Path:
    return APP_DIR / "styles.css"


@app.get("/app.js", response_class=FileResponse)
def frontend_script() -> Path:
    return APP_DIR / "app.js"


@app.get("/i18n.js", response_class=FileResponse)
def frontend_i18n() -> Path:
    return APP_DIR / "i18n.js"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    model_deployment = os.getenv("MODEL_DEPLOYMENT", "gpt-5-mini").strip()
    documents, excerpt = retrieve(request.message)
    grounded_input = create_grounded_input(
        request.message,
        documents,
        excerpt,
    )
    response_args = {
        "model": model_deployment,
        "instructions": _system_prompt_for(request.language),
        "input": grounded_input,
    }
    if request.previous_response_id:
        response_args["previous_response_id"] = request.previous_response_id

    try:
        response = get_openai_client().responses.create(**response_args)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Model request failed:\n%s", traceback.format_exc())
        raise HTTPException(status_code=502, detail=f"Model request failed: {exc}") from exc

    return ChatResponse(message=response.output_text, response_id=response.id)


@app.post("/api/knowledge/chat", response_model=KnowledgeChatResponse)
def knowledge_chat(request: ChatRequest) -> KnowledgeChatResponse:
    """Answer one source-grounded question about the reviewed website corpus."""
    model_deployment = os.getenv("MODEL_DEPLOYMENT", "gpt-5-mini").strip()
    documents, excerpt = retrieve(request.message)
    grounded_input = create_knowledge_input(request.message, documents, excerpt)
    response_args = {
        "model": model_deployment,
        "instructions": _knowledge_prompt_for(request.language),
        "input": grounded_input,
    }
    if request.previous_response_id:
        response_args["previous_response_id"] = request.previous_response_id

    try:
        response = get_openai_client().responses.create(**response_args)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Knowledge assistant request failed:\n%s", traceback.format_exc())
        raise HTTPException(status_code=502, detail=f"Knowledge assistant request failed: {exc}") from exc
    return KnowledgeChatResponse(
        message=response.output_text,
        response_id=response.id,
        sources=[
            KnowledgeChatSource(title=document.title, url=document.canonical_url)
            for document in documents
        ],
    )


@app.post("/api/contexts/prepare", response_model=BusinessContext)
def prepare_context(request: PrepareContextRequest) -> BusinessContext:
    return _prepare_business_context(request.previous_response_id)


def _prepare_business_context(previous_response_id: str) -> BusinessContext:
    model_deployment = os.getenv("MODEL_DEPLOYMENT", "gpt-5-mini").strip()

    try:
        response = get_openai_client().responses.parse(
            model=model_deployment,
            instructions=FINALIZER_PROMPT,
            input="Prepare the Business Context from the conversation for Product Owner review.",
            previous_response_id=previous_response_id,
            text_format=BusinessContext,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Context preparation failed: {exc}") from exc

    if response.output_parsed is None:
        raise HTTPException(status_code=502, detail="The model did not return a Business Context")
    return response.output_parsed


def _prepare_business_context_from_conversation(
    conversation: ConversationDetail,
) -> BusinessContext:
    model_deployment = os.getenv("MODEL_DEPLOYMENT", "gpt-5-mini").strip()
    conversation_input = [
        {"role": message.role, "content": message.content}
        for message in conversation.messages
    ]
    conversation_input.append(
        {
            "role": "user",
            "content": "Prepare the Business Context from this conversation for Product Owner review.",
        }
    )
    try:
        response = get_openai_client().responses.parse(
            model=model_deployment,
            instructions=FINALIZER_PROMPT,
            input=conversation_input,
            text_format=BusinessContext,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Context preparation failed: {exc}") from exc

    if response.output_parsed is None:
        raise HTTPException(status_code=502, detail="The model did not return a Business Context")
    return response.output_parsed


@app.get("/api/conversations", response_model=list[ConversationSummary])
def list_conversations() -> list[ConversationSummary]:
    return get_context_store().list_conversations()


@app.post("/api/conversations", response_model=ConversationDetail, status_code=201)
def create_conversation(request: ConversationCreateRequest | None = None) -> ConversationDetail:
    language = request.language if request else "en"
    return get_context_store().create_conversation(language=language)


@app.get("/api/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: str) -> ConversationDetail:
    conversation = get_context_store().get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.delete("/api/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str) -> Response:
    if not get_context_store().delete_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return Response(status_code=204)


@app.post(
    "/api/conversations/{conversation_id}/messages",
    response_model=ConversationTurnResponse,
)
def add_conversation_message(
    conversation_id: str, request: ConversationMessageRequest
) -> ConversationTurnResponse:
    store = get_context_store()
    conversation = store.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    model_deployment = os.getenv("MODEL_DEPLOYMENT", "gpt-5-mini").strip()
    documents, excerpt = retrieve(request.message)
    grounded_input = create_grounded_input(
        request.message,
        documents,
        excerpt,
    )
    response_args = {
        "model": model_deployment,
        "instructions": _system_prompt_for(conversation.language),
        "input": [
            *(
                {"role": message.role, "content": message.content}
                for message in conversation.messages
            ),
            {"role": "user", "content": grounded_input},
        ],
        "text_format": ProductStrategistTurn,
    }

    try:
        response = get_openai_client().responses.parse(**response_args)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Model request failed:\n%s", traceback.format_exc())
        raise HTTPException(status_code=502, detail=f"Model request failed: {exc}") from exc

    turn = response.output_parsed
    if turn is None:
        raise HTTPException(status_code=502, detail="The model did not return a valid response")

    updated = store.add_conversation_turn(
        conversation_id=conversation_id,
        user_message=request.message,
        assistant_message=turn.message,
        is_ready_to_save=turn.is_ready_to_save,
        readiness_reason=turn.readiness_reason,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationTurnResponse(
        conversation=updated,
        assistant_message=updated.messages[-1],
    )


@app.post(
    "/api/conversations/{conversation_id}/portfolio",
    response_model=StoredBusinessContext,
    status_code=201,
)
def save_conversation_to_portfolio(conversation_id: str) -> StoredBusinessContext:
    store = get_context_store()
    conversation = store.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conversation.portfolio_context_id:
        context = store.get(conversation.portfolio_context_id)
        if context is not None:
            return context
    if not conversation.is_ready_to_save:
        raise HTTPException(
            status_code=409,
            detail="The Business Context needs more information before it can be saved.",
        )

    context = store.create(
        _prepare_business_context_from_conversation(conversation), status="draft"
    )
    store.link_conversation_to_context(conversation_id, context.id)
    return context


@app.get("/api/contexts", response_model=list[ContextSummary])
def list_contexts() -> list[ContextSummary]:
    return get_context_store().list()


@app.get(
    "/api/portfolio/solutions",
    response_model=PortfolioSolutionCollection,
)
def list_portfolio_solutions() -> PortfolioSolutionCollection:
    """Return approved Business Contexts from the Solution Portfolio."""
    solutions = [
        context
        for context in get_context_store().list()
        if context.status == "approved"
    ]
    return PortfolioSolutionCollection(total=len(solutions), items=solutions)


@app.get(
    "/api/portfolio/sources",
    response_model=PortfolioSourceCollection,
)
def list_portfolio_sources(
    query: str | None = Query(default=None, max_length=200),
    organisation: str | None = Query(default=None, max_length=100),
    language: str | None = Query(default=None, max_length=10),
    page_type: str | None = Query(default=None, max_length=100),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
) -> PortfolioSourceCollection:
    """List and filter reviewed public website sources."""
    documents = list(load_knowledge_documents())
    if query and query.strip():
        documents, _ = retrieve(query, limit=len(documents))
    if organisation:
        documents = [item for item in documents if item.organisation == organisation]
    if language:
        documents = [item for item in documents if item.language == language]
    if page_type:
        documents = [item for item in documents if item.page_type == page_type]

    total = len(documents)
    return PortfolioSourceCollection(
        total=total,
        items=[_source_summary(document) for document in documents[offset : offset + limit]],
    )


def _source_summary(document) -> PortfolioSourceSummary:
    profile = create_website_offering_profile(document)
    return PortfolioSourceSummary(
        id=document.source_id,
        title=document.title,
        organisation=document.organisation,
        language=document.language,
        page_type=document.page_type,
        url=document.canonical_url,
        name=profile.name,
        offering_type=profile.offering_type or None,
        short_summary=profile.short_summary,
    )


@app.get(
    "/api/portfolio/sources/{source_id}",
    response_model=PortfolioSourceDetail,
)
def get_portfolio_source(source_id: str) -> PortfolioSourceDetail:
    """Return one reviewed website source with its content and provenance."""
    document = get_knowledge_document(source_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Website source not found")
    summary = _source_summary(document)
    profile = create_website_offering_profile(document)
    return PortfolioSourceDetail(
        **summary.model_dump(),
        content=document.content,
        details=[PortfolioSourceField(label=label, value=value) for label, value in profile.details],
        customer_problems_addressed=list(profile.customer_problems_addressed),
        core_capabilities=list(profile.core_capabilities),
        value_proposition=profile.value_proposition,
        differentiators=list(profile.differentiators),
        people=list(profile.people),
        target_organisations=list(profile.target_organisations),
        relevant_industries=list(profile.relevant_industries),
        relevant_roles_and_decision_makers=list(profile.relevant_roles_and_decision_makers),
        geographic_focus=list(profile.geographic_focus),
        supporting_evidence_or_knowledge_sources=list(
            profile.supporting_evidence_or_knowledge_sources
        ),
        key_marketing_messages=list(profile.key_marketing_messages),
        assumptions=list(profile.assumptions),
        open_questions=list(profile.open_questions),
        sections=[
            PortfolioSourceSection(
                title=section.title,
                introduction=section.introduction,
                items=[PortfolioSourceField(label=label, value=value) for label, value in section.items],
            )
            for section in profile.sections
        ],
    )


@app.get("/api/contexts/{context_id}", response_model=StoredBusinessContext)
def get_context(context_id: str) -> StoredBusinessContext:
    context = get_context_store().get(context_id)
    if context is None:
        raise HTTPException(status_code=404, detail="Business Context not found")
    return context


@app.post("/api/contexts", response_model=StoredBusinessContext, status_code=201)
def create_context(request: SaveContextRequest) -> StoredBusinessContext:
    return get_context_store().create(request.context, request.status)


@app.put("/api/contexts/{context_id}", response_model=StoredBusinessContext)
def update_context(context_id: str, request: SaveContextRequest) -> StoredBusinessContext:
    context = get_context_store().update(context_id, request.context, request.status)
    if context is None:
        raise HTTPException(status_code=404, detail="Business Context not found")
    return context


@app.delete("/api/contexts/{context_id}", status_code=204)
def delete_context(context_id: str) -> Response:
    if not get_context_store().delete_context(context_id):
        raise HTTPException(status_code=404, detail="Business Context not found")
    return Response(status_code=204)
