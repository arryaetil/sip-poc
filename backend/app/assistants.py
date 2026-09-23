"""Model access behind one interface, so the provider is chosen in one place.

`SIP_ASSISTANT_PROVIDER` selects the implementation at startup:

- `foundry` (default): Azure AI Foundry through the OpenAI Responses API, with
  SIP's own retrieval index.
- `dify`: three hosted Dify apps (Product Strategist, Finalizer, Knowledge
  Assistant), reached over Dify's HTTP API. Their definitions are generated from
  the same prompt files by dify/build_apps.py.

SIP owns every conversation. Each call receives the stored history and sends it
along, so a conversation can move between providers without losing context.
Endpoints in main.py call `get_assistant()` and never check which provider it is.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import hashlib
import logging
import os
import re
from typing import Protocol

import httpx
from pydantic import BaseModel, ValidationError

from app.knowledge import load_knowledge_documents
from app.models import (
    BusinessContext,
    ConversationMessage,
    KnowledgeChatSource,
    KnowledgeNearMiss,
    ProductStrategistTurn,
)

logger = logging.getLogger(__name__)

LANGUAGE_NAMES = {"en": "English", "nl": "Dutch", "de": "German"}
# Measured on the ETIL corpus: the intended document scores ~0.66, incidental
# hits on the same answer 0.50-0.60.
SOURCE_SCORE_RATIO = 0.85


class AssistantUnavailable(RuntimeError):
    """The provider is not configured; endpoints answer 503."""


class KnowledgeReply(BaseModel):
    """What the Dify knowledge app returns for a grounded (non-general) turn."""

    message: str
    answered_from_sources: bool


@dataclass
class KnowledgeAnswer:
    message: str
    response_id: str | None
    sources: list[KnowledgeChatSource]
    near_misses: list[KnowledgeNearMiss] = field(default_factory=list)


class Assistant(Protocol):
    name: str

    def strategist_turn(
        self,
        history: list[ConversationMessage],
        message: str,
        language: str,
        owner_id: str,
        extra_instructions: str = "",
    ) -> ProductStrategistTurn: ...

    def prepare_context(self, history: list[ConversationMessage], owner_id: str) -> BusinessContext: ...

    def knowledge_answer(
        self,
        history: list[ConversationMessage],
        message: str,
        language: str,
        owner_id: str,
        answer_generally: bool,
    ) -> KnowledgeAnswer: ...

    def index_upload(
        self, *, upload_id: str, owner_id: str, filename: str, content: str, visibility: str
    ) -> None: ...


# --------------------------------------------------------------------------- Foundry


def _as_input(history: list[ConversationMessage]) -> list[dict[str, str]]:
    return [{"role": item.role, "content": item.content} for item in history]


class FoundryAssistant:
    name = "foundry"

    def _client(self):
        from app.main import get_openai_client

        return get_openai_client()

    def _model(self) -> str:
        return os.getenv("MODEL_DEPLOYMENT", "gpt-5-mini").strip()

    def strategist_turn(self, history, message, language, owner_id, extra_instructions=""):
        from app.main import _system_prompt_for

        instructions = _system_prompt_for(language)
        if extra_instructions:
            instructions += f"\n\n{extra_instructions}"
        response = self._client().responses.parse(
            model=self._model(),
            instructions=instructions,
            input=[*_as_input(history), {"role": "user", "content": message}],
            text_format=ProductStrategistTurn,
        )
        if response.output_parsed is None:
            raise ValueError("The model did not return a valid response")
        return response.output_parsed

    def prepare_context(self, history, owner_id):
        from app.main import FINALIZER_PROMPT

        response = self._client().responses.parse(
            model=self._model(),
            instructions=FINALIZER_PROMPT,
            input=[
                *_as_input(history),
                {"role": "user", "content": "Prepare the Business Context from this conversation for Product Owner review."},
            ],
            text_format=BusinessContext,
        )
        if response.output_parsed is None:
            raise ValueError("The model did not return a Business Context")
        return response.output_parsed

    def knowledge_answer(self, history, message, language, owner_id, answer_generally):
        from app.main import _knowledge_prompt_for
        from app.retrieval import create_knowledge_input, retrieve_with_diagnostics

        documents, excerpt, near_misses = retrieve_with_diagnostics(message, owner_id=owner_id)
        if answer_generally:
            documents, near_misses = [], []
            grounded_input = (
                "Answer the following from general knowledge. This is explicitly not a sourced SIP answer. "
                "Do not use [Source N] citations and do not present the answer as evidence for a Business Context.\n\n"
                f"Question: {message}"
            )
            instructions = _knowledge_prompt_for(language) + (
                "\n\nThis turn is a visually and structurally separate general answer. "
                "Never invent or include SIP source citations."
            )
        else:
            grounded_input = create_knowledge_input(message, documents, excerpt)
            instructions = _knowledge_prompt_for(language)
        response = self._client().responses.create(
            model=self._model(),
            instructions=instructions,
            input=[*_as_input(history), {"role": "user", "content": grounded_input}],
        )
        return KnowledgeAnswer(
            message=response.output_text,
            response_id=response.id,
            sources=[KnowledgeChatSource(title=d.title, url=d.canonical_url) for d in documents],
            near_misses=[
                KnowledgeNearMiss(title=item.title, url=item.url, score=item.score) for item in near_misses
            ],
        )

    def index_upload(self, *, upload_id, owner_id, filename, content, visibility):
        from app.retrieval import index_uploaded_document

        index_uploaded_document(
            upload_id=upload_id, owner_id=owner_id, filename=filename, content=content, visibility=visibility
        )


# --------------------------------------------------------------------------- Dify


# Dify rejects a paragraph input of 100,000 characters or more (measured).
HISTORY_LIMIT = 95_000
OMITTED = "[Earlier messages omitted]"


def _transcript(history: list[ConversationMessage], limit: int = HISTORY_LIMIT) -> str:
    """The conversation as text, dropping the oldest messages once it gets too long."""
    labels = {"user": "User", "assistant": "Assistant"}
    parts: list[str] = []
    size = 0
    for item in reversed(history):
        part = f"{labels[item.role]}: {item.content}"
        if size + len(part) + 2 > limit - len(OMITTED) - 2:
            parts.append(OMITTED)
            break
        parts.append(part)
        size += len(part) + 2
    return "\n\n".join(reversed(parts))


def _parse_json(model: type[BaseModel], text: str) -> BaseModel:
    """Validate the app's JSON answer; tolerate a stray code fence around it."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        return model.model_validate_json(match.group(0) if match else text)
    except ValidationError as exc:
        logger.error("Dify returned invalid %s JSON: %s", model.__name__, text[:2000])
        raise ValueError(f"The model did not return a valid {model.__name__}") from exc


@lru_cache(maxsize=1)
def _documents_by_filename() -> dict[str, tuple[str, str]]:
    """Map the uploaded Dify file name back to SIP's title and canonical URL."""
    return {
        f"{document.source_id.split(':', 1)[1]}.md": (document.title, document.canonical_url)
        for document in load_knowledge_documents()
    }


class DifyAssistant:
    """Calls three Dify chatflow apps. Each app has its own API key."""

    name = "dify"

    def __init__(self) -> None:
        self.base_url = os.getenv("DIFY_API_BASE", "https://api.dify.ai/v1").strip().rstrip("/")
        self.keys = {
            "strategist": os.getenv("DIFY_STRATEGIST_API_KEY", "").strip(),
            "finalizer": os.getenv("DIFY_FINALIZER_API_KEY", "").strip(),
            "knowledge": os.getenv("DIFY_KNOWLEDGE_API_KEY", "").strip(),
        }
        missing = [f"DIFY_{app.upper()}_API_KEY" for app, key in self.keys.items() if not key]
        if missing:
            # Fail closed: refuse to start half-configured rather than fail per request.
            raise AssistantUnavailable(f"SIP_ASSISTANT_PROVIDER=dify but {', '.join(missing)} is not set")
        self.http = httpx.Client(timeout=httpx.Timeout(180.0, connect=10.0))

    def _run(self, app: str, query: str, inputs: dict[str, str], owner_id: str) -> dict:
        # Dify only needs a stable per-user label, not SIP's real user id.
        user = hashlib.sha256(owner_id.encode()).hexdigest()[:24]
        response = self.http.post(
            f"{self.base_url}/chat-messages",
            headers={"Authorization": f"Bearer {self.keys[app]}"},
            json={"query": query, "inputs": inputs, "response_mode": "blocking", "user": user},
        )
        if response.status_code >= 400:
            logger.error("Dify %s app returned %s: %s", app, response.status_code, response.text[:1000])
            raise RuntimeError(f"Dify {app} app returned {response.status_code}")
        body = response.json()
        # The inputs and answer are logged so a wrong answer can be traced to what was sent.
        logger.info(
            "dify_call app=%s message_id=%s query_chars=%s history_chars=%s",
            app,
            body.get("message_id"),
            len(query),
            len(inputs.get("history", "")),
        )
        return body

    def strategist_turn(self, history, message, language, owner_id, extra_instructions=""):
        body = self._run(
            "strategist",
            message,
            {
                "language": LANGUAGE_NAMES.get(language, "English"),
                "history": _transcript(history),
                "extra_instructions": extra_instructions,
            },
            owner_id,
        )
        return _parse_json(ProductStrategistTurn, body.get("answer", ""))

    def prepare_context(self, history, owner_id):
        body = self._run(
            "finalizer",
            "Prepare the Business Context from this conversation for Product Owner review.",
            {"history": _transcript(history)},
            owner_id,
        )
        return _parse_json(BusinessContext, body.get("answer", ""))

    def knowledge_answer(self, history, message, language, owner_id, answer_generally):
        body = self._run(
            "knowledge",
            message,
            {
                "language": LANGUAGE_NAMES.get(language, "English"),
                "history": _transcript(history),
                "general": "yes" if answer_generally else "no",
            },
            owner_id,
        )
        if answer_generally:
            return KnowledgeAnswer(message=body.get("answer", ""), response_id=body.get("message_id"), sources=[])
        try:
            reply = _parse_json(KnowledgeReply, body.get("answer", ""))
        except ValueError:
            # An app published before the JSON answer existed returns plain text.
            reply = KnowledgeReply(message=body.get("answer", ""), answered_from_sources=True)
        if not reply.answered_from_sources:
            # Greeting, or the corpus does not hold the answer: list no sources, so the
            # UI offers a general answer exactly as it does on the Foundry path.
            return KnowledgeAnswer(message=reply.message, response_id=body.get("message_id"), sources=[])
        resources = body.get("metadata", {}).get("retriever_resources", []) or []
        top = max((resource.get("score") or 0 for resource in resources), default=0)
        sources: list[KnowledgeChatSource] = []
        seen: set[str] = set()
        known = _documents_by_filename()
        for resource in resources:
            # Show only documents close to the best match; the rest is incidental.
            if (resource.get("score") or 0) < SOURCE_SCORE_RATIO * top:
                continue
            title, url = known.get(resource.get("document_name", ""), (resource.get("document_name", ""), ""))
            if url in seen or not title:
                continue
            seen.add(url)
            sources.append(KnowledgeChatSource(title=title, url=url))
        return KnowledgeAnswer(message=reply.message, response_id=body.get("message_id"), sources=sources)

    def index_upload(self, *, upload_id, owner_id, filename, content, visibility):
        # Uploads are deliberately not sent to a Dify knowledge base: that would place
        # user documents outside Azure without a processing agreement. The file and its
        # extracted text are still stored by SIP and used when a document is discussed.
        logger.info("dify provider: upload %s stored but not indexed", upload_id)


# --------------------------------------------------------------------------- selection


@lru_cache(maxsize=1)
def get_assistant() -> Assistant:
    provider = os.getenv("SIP_ASSISTANT_PROVIDER", "foundry").strip().casefold() or "foundry"
    if provider == "foundry":
        return FoundryAssistant()
    if provider == "dify":
        return DifyAssistant()
    raise AssistantUnavailable(f"Unknown SIP_ASSISTANT_PROVIDER '{provider}' (use foundry or dify)")
