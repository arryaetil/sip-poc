from typing import Literal

from pydantic import BaseModel, Field, field_validator


class BusinessContext(BaseModel):
    name: str
    offering_type: Literal["product", "service"]
    short_summary: str
    customer_problems_addressed: list[str]
    core_capabilities: list[str]
    target_organisations: list[str]
    relevant_industries: list[str]
    relevant_roles_and_decision_makers: list[str]
    geographic_focus: list[str]
    value_proposition: str
    differentiators: list[str]
    people: list[str]
    supporting_evidence_or_knowledge_sources: list[str]
    key_marketing_messages: list[str]
    assumptions: list[str]
    open_questions: list[str]


class PrepareContextRequest(BaseModel):
    previous_response_id: str


class ConversationMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10_000)


class KnowledgeChatSource(BaseModel):
    title: str
    url: str
    # web: a public page, opened directly. upload/context: shown in the source viewer.
    kind: Literal["web", "upload", "context"] = "web"
    item_id: str | None = None
    # The retrieved text the answer was based on, so the viewer can show it.
    passages: list[str] = Field(default_factory=list)


class KnowledgeNearMiss(KnowledgeChatSource):
    score: float


class MarketingRequest(BaseModel):
    """A request for marketing material, recognised by the knowledge assistant."""

    format: Literal["linkedin_post", "one_pager", "presentation"]
    brief: str
    title: str = ""
    brand: Literal["etil", "ibc-group"] = "etil"


class KnowledgeChatResponse(BaseModel):
    message: str
    response_id: str | None = None
    sources: list[KnowledgeChatSource]
    near_misses: list[KnowledgeNearMiss] = Field(default_factory=list)
    conversation_id: str
    general_answer_available: bool = False
    # Set when the user asked for marketing material; the UI offers the studio.
    marketing_request: MarketingRequest | None = None


class StudioProjectRequest(BaseModel):
    marketing_request: MarketingRequest
    conversation_id: str | None = None
    sources: list[KnowledgeChatSource] = Field(default_factory=list, max_length=12)


class ConversationCreateRequest(BaseModel):
    language: Literal["en", "nl", "de"] = "en"
    kind: Literal["context", "knowledge", "product_owner"] = "context"


class UserInfo(BaseModel):
    email: str
    role: Literal["admin", "product_owner", "sales"]


class UserRecord(BaseModel):
    id: str
    email: str
    role: Literal["admin", "product_owner", "sales"]
    created_at: str
    updated_at: str


class CreateUserRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=200)
    role: Literal["admin", "product_owner", "sales"]


class UpdateUserRequest(BaseModel):
    role: Literal["admin", "product_owner", "sales"] | None = None
    password: str | None = Field(default=None, min_length=8, max_length=200)


class ProductStrategistTurn(BaseModel):
    message: str
    is_ready_to_save: bool
    readiness_reason: str


class ConversationMessage(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    content: str
    created_at: str


class ConversationSummary(BaseModel):
    id: str
    title: str
    preview: str
    language: Literal["en", "nl", "de"]
    kind: Literal["context", "knowledge", "product_owner"] = "context"
    is_ready_to_save: bool
    readiness_reason: str
    portfolio_context_id: str | None
    message_count: int
    created_at: str
    updated_at: str


class ConversationDetail(ConversationSummary):
    messages: list[ConversationMessage]


class ConversationTurnResponse(BaseModel):
    conversation: ConversationDetail
    assistant_message: ConversationMessage


class SaveContextRequest(BaseModel):
    context: BusinessContext
    status: Literal["draft", "approved"]
    publish_upload_ids: list[str] = Field(default_factory=list)


class StoredBusinessContext(BusinessContext):
    id: str
    status: Literal["draft", "approved"]
    created_at: str
    updated_at: str


class ContextSummary(BaseModel):
    id: str
    name: str
    offering_type: Literal["product", "service"]
    short_summary: str
    relevant_industries: list[str]
    geographic_focus: list[str]
    status: Literal["draft", "approved"]
    updated_at: str


class PortfolioSolutionCollection(BaseModel):
    total: int
    items: list[ContextSummary]


class PortfolioSourceSummary(BaseModel):
    id: str
    title: str
    organisation: str
    language: str
    page_type: str
    url: str
    name: str | None = None
    offering_type: Literal["product", "service"] | None = None
    short_summary: str | None = None


class PortfolioSourceField(BaseModel):
    label: str
    value: str


class PortfolioSourceSection(BaseModel):
    title: str
    introduction: str
    items: list[PortfolioSourceField]


class PortfolioSourceDetail(PortfolioSourceSummary):
    """A website source presented in the same field structure as a BusinessContext.

    Every BusinessContext field is present so the portfolio renders one consistent
    layout. Fields that a public website page cannot supply stay empty on purpose:
    a scraped page has no Product Owner, so it has no validated assumptions or open
    questions. Empty means "the page does not say", never "we could not be bothered".
    """

    content: str
    details: list[PortfolioSourceField] = Field(default_factory=list)
    customer_problems_addressed: list[str] = Field(default_factory=list)
    core_capabilities: list[str] = Field(default_factory=list)
    value_proposition: str = ""
    differentiators: list[str] = Field(default_factory=list)
    people: list[str] = Field(default_factory=list)
    target_organisations: list[str] = Field(default_factory=list)
    relevant_industries: list[str] = Field(default_factory=list)
    relevant_roles_and_decision_makers: list[str] = Field(default_factory=list)
    geographic_focus: list[str] = Field(default_factory=list)
    supporting_evidence_or_knowledge_sources: list[str] = Field(default_factory=list)
    key_marketing_messages: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    sections: list[PortfolioSourceSection] = Field(default_factory=list)


class PortfolioSourceCollection(BaseModel):
    total: int
    items: list[PortfolioSourceSummary]


class UploadRecord(BaseModel):
    id: str
    kind: Literal["context_evidence", "workspace"]
    filename: str
    media_type: str
    size_bytes: int
    page_count: int | None
    visibility: Literal["org", "private"]
    context_id: str | None = None
    conversation_id: str | None = None
    created_at: str


FIBONACCI_POINTS = (1, 2, 3, 5, 8, 13, 21)
StoryPoints = Literal[1, 2, 3, 5, 8, 13, 21]


def _clean_text(value: str, limit: int) -> str:
    value = (value or "").strip()
    if len(value) > limit:
        raise ValueError(f"must be at most {limit} characters")
    return value


def _clean_items(items: list[str]) -> list[str]:
    cleaned = [item.strip() for item in items or [] if item and item.strip()]
    if len(cleaned) > 30 or any(len(item) > 1000 for item in cleaned):
        raise ValueError("at most 30 items of 1000 characters")
    return cleaned


class StoryDraftContent(BaseModel):
    """A user story as the Product Owner assistant proposes it and the user edits it.

    No approval, execution or success fields: those decisions belong to SIP,
    never to the model. Limits are validators, not schema keywords, so the same
    model can serve as an OpenAI strict schema.
    """

    title: str = ""
    role: str = ""
    capability: str = ""
    value: str = ""
    entry_criteria: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    story_points: StoryPoints | None = None
    estimation_reason: str = ""
    target_kind: Literal["backlog", "sprint"] | None = None
    iteration_path: str | None = None

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        return _clean_text(value, 255)

    @field_validator("role", "capability", "value", "estimation_reason")
    @classmethod
    def _text(cls, value: str) -> str:
        return _clean_text(value, 2000)

    @field_validator("entry_criteria", "acceptance_criteria")
    @classmethod
    def _items(cls, value: list[str]) -> list[str]:
        return _clean_items(value)

    @field_validator("iteration_path")
    @classmethod
    def _path(cls, value: str | None) -> str | None:
        return _clean_text(value, 400) or None if value is not None else None


class ProductOwnerTurn(BaseModel):
    """One answer of the Product Owner app in Dify (or Foundry)."""

    message: str
    stage: Literal["clarifying", "draft_ready"]
    draft: StoryDraftContent | None = None
    # At most one current question; the rule is "one question at a time".
    open_questions: list[str] = Field(default_factory=list)
    # Titles of smaller stories when the work is too big for one.
    split_suggestion: list[str] = Field(default_factory=list)

    @field_validator("open_questions")
    @classmethod
    def _one_question(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()][:1]

    @field_validator("split_suggestion")
    @classmethod
    def _split(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()][:8]


StoryDraftStatus = Literal["draft", "creating", "created", "failed", "uncertain"]


class StoryDraftRecord(BaseModel):
    """A story proposal as SIP stores it: versioned, owned, with its DevOps outcome."""

    id: str
    conversation_id: str
    version: int
    status: StoryDraftStatus
    content: StoryDraftContent
    description: str
    missing: list[str]
    approved_version: int | None = None
    approved_at: str | None = None
    devops_id: int | None = None
    devops_url: str | None = None
    error: str | None = None
    created_at: str
    updated_at: str


class ProductOwnerChatResponse(BaseModel):
    message: str
    conversation_id: str
    draft: StoryDraftRecord | None = None
    open_questions: list[str] = Field(default_factory=list)
    split_suggestion: list[str] = Field(default_factory=list)


class UpdateStoryDraftRequest(BaseModel):
    version: int
    content: StoryDraftContent


class CreateStoryRequest(BaseModel):
    # The version the user saw when they confirmed; a newer version needs a new confirmation.
    version: int
    # One id per confirmation click: a repeated request with it never writes twice.
    confirmation_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9-]+$")


class StoryTarget(BaseModel):
    kind: Literal["backlog", "sprint"]
    name: str
    iteration_path: str
    timeframe: Literal["current", "future", ""] = ""
    start: str | None = None
    finish: str | None = None


class ProductOwnerSettings(BaseModel):
    devops_configured: bool
    can_create: bool
    organisation: str
    project: str
    targets: list[StoryTarget]
    notice: str | None = None


class CreatedStory(BaseModel):
    id: int
    url: str
    title: str
    iteration_path: str
