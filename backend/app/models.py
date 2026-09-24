from typing import Literal

from pydantic import BaseModel, Field


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


class KnowledgeChatResponse(BaseModel):
    message: str
    response_id: str | None = None
    sources: list[KnowledgeChatSource]
    near_misses: list[KnowledgeNearMiss] = Field(default_factory=list)
    conversation_id: str
    general_answer_available: bool = False


class ConversationCreateRequest(BaseModel):
    language: Literal["en", "nl", "de"] = "en"
    kind: Literal["context", "knowledge"] = "context"


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
    kind: Literal["context", "knowledge"] = "context"
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
