import re
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

    format: Literal["linkedin_post", "instagram_carousel", "one_pager", "presentation"]
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
    kind: Literal["context", "knowledge", "product_owner", "lead"] = "context"
    # Set to update an approved Business Context through the conversation.
    updates_context_id: str | None = None


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
    kind: Literal["context", "knowledge", "product_owner", "lead"] = "context"
    is_ready_to_save: bool
    readiness_reason: str
    portfolio_context_id: str | None
    updates_context_id: str | None = None
    website_source_id: str | None = None
    context_intent: Literal["pending", "create", "update", "website"] = "pending"
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
    # How the change was made, for the version history.
    source: Literal["form", "conversation"] = "form"
    conversation_id: str | None = None  # the update conversation these changes came from
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
WorkItemType = Literal["User Story", "Bug", "Task", "Feature", "Epic"]
Priority = Literal[1, 2, 3, 4]


def _clean_text(value: str, limit: int) -> str:
    value = (value or "").strip()
    if len(value) > limit:
        raise ValueError(f"must be at most {limit} characters")
    return value


# SIP writes "As … I want … so that …" itself; a part that repeats those words
# would read "zodat zodat". Stripped for model output and user edits alike.
_LEADING_WORDS = {
    "role": re.compile(r"^\s*(als|as)\s+", re.IGNORECASE),
    "capability": re.compile(r"^\s*(wil ik|i want|ich möchte|möchte ich)\s+", re.IGNORECASE),
    "value": re.compile(r"^\s*(zodat|so that|damit)\s+", re.IGNORECASE),
}


def _strip_leading(part: str, value: str | None) -> str | None:
    if not value:
        return value
    pattern = _LEADING_WORDS[part]
    while pattern.match(value):
        value = pattern.sub("", value, count=1)
    return value


def _clean_items(items: list[str]) -> list[str]:
    cleaned = [item.strip() for item in items or [] if item and item.strip()]
    if len(cleaned) > 30 or any(len(item) > 1000 for item in cleaned):
        raise ValueError("at most 30 items of 1000 characters")
    return cleaned


def _clean_tags(items: list[str] | None) -> list[str]:
    seen: dict[str, str] = {}
    for item in items or []:
        for part in str(item).split(";"):
            tag = part.strip()
            if tag and tag.casefold() not in seen:
                seen[tag.casefold()] = tag
    if len(seen) > 20 or any(len(tag) > 100 for tag in seen.values()):
        raise ValueError("at most 20 tags of 100 characters")
    return list(seen.values())


class StoryDraftContent(BaseModel):
    """A user story as the Product Owner assistant proposes it and the user edits it.

    No approval, execution or success fields: those decisions belong to SIP,
    never to the model. Limits are validators, not schema keywords, so the same
    model can serve as an OpenAI strict schema.
    """

    work_item_type: WorkItemType = "User Story"
    title: str = ""
    role: str = ""
    capability: str = ""
    value: str = ""
    # Plain text for every type except a user story (repro steps for a bug).
    description: str = ""
    entry_criteria: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    story_points: StoryPoints | None = None
    estimation_reason: str = ""
    # Hours of work left, for a task or a bug.
    remaining_work: float | None = None
    priority: Priority | None = None
    # The work item this one belongs under (a task under a story, a story under a feature).
    parent_id: int | None = None
    target_kind: Literal["backlog", "sprint"] | None = None
    iteration_path: str | None = None
    # The language the story text is written in; SIP builds "As … I want … so that …"
    # in it, which can differ from the interface language.
    language: Literal["nl", "en", "de"] | None = None
    # A team member's display name; SIP resolves it to the real account. None = nobody.
    assigned_to: str | None = None
    # Existing Azure DevOps tags only; SIP drops or refuses tags that do not exist.
    tags: list[str] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        return _clean_text(value, 255)

    @field_validator("tags")
    @classmethod
    def _tags(cls, value: list[str]) -> list[str]:
        return _clean_tags(value)

    @field_validator("role", "capability", "value", "estimation_reason")
    @classmethod
    def _text(cls, value: str, info) -> str:
        value = _clean_text(value, 2000)
        return _strip_leading(info.field_name, value) if info.field_name in _LEADING_WORDS else value

    @field_validator("description")
    @classmethod
    def _description(cls, value: str) -> str:
        return _clean_text(value, 8000)

    @field_validator("remaining_work")
    @classmethod
    def _hours(cls, value: float | None) -> float | None:
        if value is not None and not 0 <= value <= 1000:
            raise ValueError("remaining work must be between 0 and 1000 hours")
        return value

    @field_validator("entry_criteria", "acceptance_criteria")
    @classmethod
    def _items(cls, value: list[str]) -> list[str]:
        return _clean_items(value)

    @field_validator("iteration_path")
    @classmethod
    def _path(cls, value: str | None) -> str | None:
        return _clean_text(value, 400) or None if value is not None else None


# SIP never sets these: Closed is the product owner's acceptance step in Azure
# DevOps itself and Removed takes work away. Checked on every change.
FORBIDDEN_STATES = ("Closed", "Removed")


class WorkItemQuery(BaseModel):
    """A read the assistant asks SIP to do; SIP runs it, the model never calls Azure DevOps."""

    kind: Literal["sprint", "assigned", "story", "search", "children"]
    # sprint: an iteration path from the available targets, or null for the current sprint.
    # assigned: optionally limits the list to that sprint.
    iteration_path: str | None = None
    # assigned: a display name from the team list, or "me" for the signed-in user.
    person: str | None = None
    # story / children: the work item number.
    work_item_id: int | None = None
    # search: words in the title, a type, a status, or only items not planned in a sprint.
    text: str | None = None
    work_item_type: WorkItemType | None = None
    state: str | None = None
    unplanned: bool | None = None


class WorkItemChange(BaseModel):
    """Proposed changes to an existing work item. Null means: leave this field as it is."""

    work_item_id: int
    title: str | None = None
    # role, capability and value together rewrite the description as "As … I want … so that …".
    role: str | None = None
    capability: str | None = None
    value: str | None = None
    # Plain text description for every type except a user story (repro steps for a bug).
    description: str | None = None
    entry_criteria: list[str] | None = None
    acceptance_criteria: list[str] | None = None
    story_points: StoryPoints | None = None
    estimation_reason: str | None = None
    remaining_work: float | None = None
    priority: Priority | None = None
    parent_id: int | None = None
    # A comment for the item's discussion, written together with the change.
    comment: str | None = None
    # Checked by SIP against the item type's live states; never Closed or Removed.
    state: str | None = None
    target_kind: Literal["backlog", "sprint"] | None = None
    iteration_path: str | None = None
    assigned_to: str | None = None
    # Existing tags to add or remove; the rest of the story's tags stay.
    add_tags: list[str] | None = None
    remove_tags: list[str] | None = None
    language: Literal["nl", "en", "de"] | None = None

    @field_validator("add_tags", "remove_tags")
    @classmethod
    def _tags(cls, value: list[str] | None) -> list[str] | None:
        return _clean_tags(value) if value is not None else None

    @field_validator("title")
    @classmethod
    def _title(cls, value: str | None) -> str | None:
        return _clean_text(value, 255) or None if value is not None else None

    @field_validator("role", "capability", "value", "estimation_reason", "iteration_path", "assigned_to", "state")
    @classmethod
    def _text(cls, value: str | None, info) -> str | None:
        value = _clean_text(value, 2000) or None if value is not None else None
        return _strip_leading(info.field_name, value) if info.field_name in _LEADING_WORDS else value

    @field_validator("description", "comment")
    @classmethod
    def _long_text(cls, value: str | None) -> str | None:
        return _clean_text(value, 8000) or None if value is not None else None

    @field_validator("entry_criteria", "acceptance_criteria")
    @classmethod
    def _items(cls, value: list[str] | None) -> list[str] | None:
        return _clean_items(value) if value is not None else None


class ProductOwnerTurn(BaseModel):
    """One answer of the Product Owner app in Dify (or Foundry).

    At most one of draft (new story), query (read) or change (update an
    existing story) is filled per turn.
    """

    message: str
    stage: Literal["clarifying", "draft_ready", "answer", "change_ready"]
    draft: StoryDraftContent | None = None
    query: WorkItemQuery | None = None
    change: WorkItemChange | None = None
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


class WorkItemSummary(BaseModel):
    id: int
    title: str
    work_item_type: str
    state: str
    story_points: float | None = None
    assigned_to: str | None = None
    iteration_path: str = ""
    url: str


class WorkItemDetail(WorkItemSummary):
    rev: int
    tags: list[str] = Field(default_factory=list)
    priority: int | None = None
    remaining_work: float | None = None
    parent_id: int | None = None
    # Position of the parent link among the item's relations (to replace it).
    parent_relation: int | None = None
    child_ids: list[int] = Field(default_factory=list)
    description: str = ""
    entry_criteria: str = ""
    acceptance_criteria: str = ""


class WorkItemResult(BaseModel):
    """What SIP read from Azure DevOps for one question, kept with the conversation."""

    id: str
    conversation_id: str
    kind: Literal["sprint", "assigned", "story", "search", "children"]
    label: str
    items: list[WorkItemSummary] = Field(default_factory=list)
    detail: WorkItemDetail | None = None
    error: str | None = None
    created_at: str


class FieldChange(BaseModel):
    field: Literal[
        "title", "description", "entry_criteria", "acceptance_criteria",
        "story_points", "state", "iteration_path", "assigned_to", "tags",
        "remaining_work", "priority", "parent", "comment",
    ]
    before: str
    after: str


WorkItemChangeStatus = Literal["draft", "applying", "applied", "failed", "uncertain"]


class WorkItemChangeRecord(BaseModel):
    id: str
    conversation_id: str
    work_item_id: int
    work_item_type: str = "User Story"
    title: str
    url: str
    version: int
    status: WorkItemChangeStatus
    changes: list[FieldChange]
    base_rev: int
    approved_version: int | None = None
    error: str | None = None
    created_at: str
    updated_at: str


class ProductOwnerTimeline(BaseModel):
    drafts: list[StoryDraftRecord]
    changes: list[WorkItemChangeRecord]
    results: list[WorkItemResult]


class ProductOwnerChatResponse(BaseModel):
    message: str
    conversation_id: str
    draft: StoryDraftRecord | None = None
    result: WorkItemResult | None = None
    change: WorkItemChangeRecord | None = None
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
    # Team members' display names, for assigning; only for accounts that may use Azure DevOps.
    people: list[str] = Field(default_factory=list)
    # Existing tags in the project; only these can be used.
    tags: list[str] = Field(default_factory=list)
    notice: str | None = None


class CreatedStory(BaseModel):
    id: int
    url: str
    title: str
    iteration_path: str
