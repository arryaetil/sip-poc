const views = {
  conversations: document.querySelector("#conversations-view"),
  builder: document.querySelector("#builder-view"),
  review: document.querySelector("#review-view"),
  portfolio: document.querySelector("#portfolio-view"),
  source: document.querySelector("#source-view"),
  knowledge: document.querySelector("#knowledge-view"),
  lead: document.querySelector("#lead-view"),
  marketing: document.querySelector("#marketing-view"),
  team: document.querySelector("#team-view"),
};

const chatForm = document.querySelector("#chat-form");
const input = document.querySelector("#message");
const messages = document.querySelector("#messages");
const send = document.querySelector("#send");
const saveToPortfolio = document.querySelector("#save-to-portfolio");
const chatStatus = document.querySelector("#chat-status");
const readiness = document.querySelector("#readiness");
const readinessText = document.querySelector("#readiness-text");
const builderTitle = document.querySelector("#builder-title");
const conversationList = document.querySelector("#conversation-list");
const contextForm = document.querySelector("#context-form");
const reviewStatus = document.querySelector("#review-status");
const reviewState = document.querySelector("#review-state");
const reviewTitle = document.querySelector("#review-title");
const approvalDocumentsSection = document.querySelector("#approval-documents-section");
const approvalDocumentsList = document.querySelector("#approval-documents-list");
const backFromReview = document.querySelector("#back-to-chat");
const portfolioList = document.querySelector("#portfolio-list");
const portfolioCount = document.querySelector("#portfolio-count");
const portfolioSearch = document.querySelector("#portfolio-search");
const portfolioFilterType = document.querySelector("#portfolio-filter-type");
const portfolioFilterOrigin = document.querySelector("#portfolio-filter-origin");
const portfolioCreate = document.querySelector("#portfolio-create");
const sourceTitle = document.querySelector("#source-title");
const sourceOrigin = document.querySelector("#source-origin");
const sourceName = document.querySelector("#source-name");
const sourceSummary = document.querySelector("#source-summary");
const sourceOrganisation = document.querySelector("#source-organisation");
const sourceLanguage = document.querySelector("#source-language");
const sourceType = document.querySelector("#source-type");
const sourcePageType = document.querySelector("#source-page-type");
const sourceProblemsField = document.querySelector("#source-problems-field");
const sourceCapabilitiesField = document.querySelector("#source-capabilities-field");
const sourceProblems = document.querySelector("#source-problems");
const sourceCapabilities = document.querySelector("#source-capabilities");
const sourceValue = document.querySelector("#source-value");
const sourceDifferentiators = document.querySelector("#source-differentiators");
const sourcePeople = document.querySelector("#source-people");
const sourceTargetOrganisations = document.querySelector("#source-target-organisations");
const sourceRelevantIndustries = document.querySelector("#source-relevant-industries");
const sourceRelevantRoles = document.querySelector("#source-relevant-roles");
const sourceGeographicFocus = document.querySelector("#source-geographic-focus");
const sourceEvidence = document.querySelector("#source-evidence");
const sourceMarketingMessages = document.querySelector("#source-marketing-messages");
const sourceAssumptions = document.querySelector("#source-assumptions");
const sourceOpenQuestions = document.querySelector("#source-open-questions");
const sourceOriginal = document.querySelector("#source-original");
const sourceContent = document.querySelector("#source-content");
const sourceOpenOriginal = document.querySelector("#source-open-original");
const knowledgeChatForm = document.querySelector("#knowledge-chat-form");
const knowledgeInput = document.querySelector("#knowledge-message");
const knowledgeMessages = document.querySelector("#knowledge-messages");
const knowledgeSend = document.querySelector("#knowledge-send");
const knowledgeStatus = document.querySelector("#knowledge-status");
const contextUpload = document.querySelector("#context-upload");
const knowledgeUpload = document.querySelector("#knowledge-upload");
const newKnowledgeChat = document.querySelector("#new-knowledge-chat");
const knowledgeHistory = document.querySelector("#knowledge-history");
const knowledgeHome = document.querySelector("#knowledge-home");
const knowledgeChat = document.querySelector("#knowledge-chat");
const knowledgeConversationList = document.querySelector("#knowledge-conversation-list");
const knowledgeStartForm = document.querySelector("#knowledge-start-form");
const knowledgeStartMessage = document.querySelector("#knowledge-start-message");
const knowledgeStartSend = document.querySelector("#knowledge-start-send");
const newConversationButton = document.querySelector("#new-conversation");
const conversationStartForm = document.querySelector("#conversation-start-form");
const conversationStartMessage = document.querySelector("#conversation-start-message");
const conversationStartSend = document.querySelector("#conversation-start-send");
const navCreateContext = document.querySelector("#nav-create-context");
const deleteDialog = document.querySelector("#delete-dialog");
const deleteTitle = document.querySelector("#delete-title");
const deleteDescription = document.querySelector("#delete-description");
const confirmDelete = document.querySelector("#confirm-delete");
const languageSwitcher = document.querySelector("#language-switcher");
const roleBadge = document.querySelector("#user-role-badge");
const saveDraftButton = document.querySelector("#save-draft");
const approveContextButton = document.querySelector("#approve-context");
const navTeam = document.querySelector("#nav-team");
const navLabelAdministration = document.querySelector("#nav-label-administration");
const createUserForm = document.querySelector("#create-user-form");
const teamStatus = document.querySelector("#team-status");
const teamList = document.querySelector("#team-list");

const contextFields = [
  "name",
  "offering_type",
  "short_summary",
  "customer_problems_addressed",
  "core_capabilities",
  "target_organisations",
  "relevant_industries",
  "relevant_roles_and_decision_makers",
  "geographic_focus",
  "value_proposition",
  "differentiators",
  "people",
  "supporting_evidence_or_knowledge_sources",
  "key_marketing_messages",
  "assumptions",
  "open_questions",
];

const listFields = new Set(
  [...contextForm.querySelectorAll("[data-list]")].map((field) => field.name),
);

let currentConversation = null;
let currentContextId = null;
let reviewOrigin = "portfolio";
let portfolioContexts = [];
let portfolioSources = [];
let knowledgeConversationId = null;
let pendingDelete = null;
let currentRole = "admin";
let currentUserEmail = "";
let acceptedDocumentProposals = [];

async function api(path, options = {}) {
  const isFormData = options.body instanceof FormData;
  const response = await fetch(path, {
    ...options,
    headers: { ...(isFormData ? {} : { "Content-Type": "application/json" }), ...(options.headers || {}) },
  });
  if (response.status === 204) return null;
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || "The request failed");
  return data;
}

async function loadCurrentUser() {
  try {
    const user = await api("/api/auth/me");
    currentRole = user.role || "admin";
    currentUserEmail = user.email || "";
  } catch (error) {
    currentRole = "admin";
  }
  roleBadge.textContent = t(`role.${currentRole}`);
  roleBadge.hidden = false;
  applyRolePermissions();
}

function applyRolePermissions() {
  const canEdit = currentRole !== "sales";
  navCreateContext.hidden = !canEdit;
  newConversationButton.hidden = !canEdit;
  portfolioCreate.hidden = !canEdit;
  saveDraftButton.hidden = !canEdit;
  approveContextButton.hidden = !canEdit;
  [...contextForm.elements].forEach((field) => {
    if (field.name) field.disabled = !canEdit;
  });

  const isAdmin = currentRole === "admin";
  navTeam.hidden = !isAdmin;
  navLabelAdministration.hidden = !isAdmin;
}

function deleteButton(label, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "delete-icon";
  button.setAttribute("aria-label", label);
  button.title = label;
  button.innerHTML = '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3m-8 0 1 13h8l1-13M10 11v5m4-5v5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  button.addEventListener("click", onClick);
  return button;
}

function requestDelete(kind, id, name) {
  pendingDelete = { kind, id };
  deleteTitle.textContent = t("delete.heading", { name });
  if (kind === "conversation") {
    deleteDescription.textContent = t("delete.conversation_description");
    confirmDelete.textContent = t("delete.conversation_title");
  } else {
    deleteDescription.textContent = t("delete.context_description");
    confirmDelete.textContent = t("delete.item_title");
  }
  deleteDialog.showModal();
}

function setStatus(element, message, type = "error") {
  element.textContent = message;
  element.classList.toggle("success", type === "success");
}

function showView(name) {
  Object.entries(views).forEach(([viewName, element]) => {
    element.hidden = viewName !== name;
  });
  document.body.classList.toggle("chat-open", name === "builder" || (name === "knowledge" && !knowledgeChat.hidden));
  const navigationView = name === "builder" || (name === "review" && reviewOrigin === "builder")
    ? "conversations"
    : name === "review" || name === "source" ? "portfolio" : name;
  document.querySelectorAll(".nav-item[data-view]").forEach((item) => {
    const active = item.dataset.view === navigationView;
    item.classList.toggle("active", active);
    if (active) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function resizeTextArea(textarea) {
  textarea.style.height = "auto";
  textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`;
}

function appendMessage(container, text, role, assistantName) {
  const row = document.createElement("div");
  row.className = `message-row ${role}`;
  if (role === "assistant") {
    const avatar = document.createElement("span");
    avatar.className = "avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = "SIP";
    row.append(avatar);
  }
  const content = document.createElement("div");
  content.className = "message-content";
  if (role === "assistant") {
    const author = document.createElement("span");
    author.className = "message-author";
    author.textContent = assistantName;
    content.append(author);
  }
  const message = document.createElement("p");
  message.className = "message";
  message.textContent = text;
  content.append(message);
  row.append(content);
  container.append(row);
  container.scrollTop = container.scrollHeight;
  return row;
}

function addMessage(text, role) {
  return appendMessage(messages, text, role, t("assistant.name"));
}

function renderConversation(conversation) {
  currentConversation = conversation;
  builderTitle.textContent = conversation.title;
  messages.replaceChildren();
  if (!conversation.messages.length) {
    addMessage(t("assistant.first_message"), "assistant");
  } else {
    conversation.messages.forEach((message) => addMessage(message.content, message.role));
  }

  const isSaved = Boolean(conversation.portfolio_context_id);
  readiness.hidden = !conversation.is_ready_to_save && !isSaved;
  readiness.dataset.ready = String(conversation.is_ready_to_save && !isSaved);
  if (isSaved) {
    readinessText.textContent = t("builder.saved_note");
    saveToPortfolio.textContent = t("builder.saved_to_portfolio");
    saveToPortfolio.disabled = true;
  } else if (conversation.is_ready_to_save) {
    readinessText.textContent = conversation.readiness_reason || t("builder.ready_note_default");
    saveToPortfolio.textContent = t("builder.save_to_portfolio");
    saveToPortfolio.disabled = false;
  } else {
    readinessText.textContent = conversation.readiness_reason || t("builder.not_ready_default");
    saveToPortfolio.textContent = t("builder.save_to_portfolio");
    saveToPortfolio.disabled = true;
  }
  setStatus(chatStatus, "");
}

async function createConversation() {
  try {
    const conversation = await api("/api/conversations", {
      method: "POST",
      body: JSON.stringify({ language: getLanguage() }),
    });
    renderConversation(conversation);
    showView("builder");
    input.focus();
  } catch (error) {
    conversationList.textContent = error.message;
  }
}

conversationStartForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = conversationStartMessage.value.trim();
  if (!message) return;
  conversationStartSend.disabled = true;
  conversationStartMessage.value = "";
  currentConversation = null;
  builderTitle.textContent = message.length > 64 ? `${message.slice(0, 61)}…` : message;
  messages.replaceChildren();
  addMessage(message, "user");
  readiness.hidden = true;
  showView("builder");
  setStatus(chatStatus, t("builder.thinking"), "success");
  try {
    const conversation = await api("/api/conversations", {
      method: "POST",
      body: JSON.stringify({ language: getLanguage(), kind: "context" }),
    });
    const turn = await api(`/api/conversations/${conversation.id}/messages`, {
      method: "POST",
      body: JSON.stringify({ message }),
    });
    renderConversation(turn.conversation);
    input.focus();
  } catch (error) {
    addMessage(error instanceof TypeError ? t("builder.unreachable") : error.message, "assistant");
    setStatus(chatStatus, "");
  } finally {
    conversationStartSend.disabled = false;
  }
});

async function openConversation(conversationId) {
  showView("builder");
  messages.replaceChildren();
  builderTitle.textContent = t("builder.title_default");
  readiness.hidden = true;
  setStatus(chatStatus, t("builder.loading"), "success");
  try {
    renderConversation(await api(`/api/conversations/${conversationId}`));
    input.focus();
  } catch (error) {
    addMessage(error.message, "assistant");
    setStatus(chatStatus, "");
  }
}

function formatDate(value) {
  const normalised = /(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value.replace(" ", "T")}Z`;
  const date = new Date(normalised);
  return Number.isNaN(date.valueOf())
    ? value
    : new Intl.DateTimeFormat(getLanguage(), { day: "2-digit", month: "short", year: "numeric" }).format(date);
}

function conversationState(conversation) {
  if (conversation.portfolio_context_id) return { label: t("state.in_portfolio"), className: "approved" };
  if (conversation.is_ready_to_save) return { label: t("state.ready"), className: "ready" };
  if (conversation.message_count) return { label: t("state.building"), className: "draft" };
  return { label: t("state.not_started"), className: "draft" };
}

function renderConversations(conversations) {
  conversationList.replaceChildren();
  if (!conversations.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    const title = document.createElement("h2");
    title.textContent = t("conversations.empty_title");
    const copy = document.createElement("p");
    copy.textContent = t("conversations.empty_copy");
    empty.append(title, copy);
    if (currentRole !== "sales") {
      const action = document.createElement("button");
      action.type = "button";
      action.className = "primary-button";
      action.textContent = t("conversations.new");
      action.addEventListener("click", createConversation);
      empty.append(action);
    }
    conversationList.append(empty);
    return;
  }

  conversations.forEach((conversation) => {
    const row = document.createElement("div");
    row.className = "conversation-row";
    const open = document.createElement("button");
    open.type = "button";
    open.className = "row-open";
    open.addEventListener("click", () => openConversation(conversation.id));
    const description = document.createElement("span");
    const title = document.createElement("span");
    title.className = "conversation-title";
    title.textContent = conversation.title;
    const preview = document.createElement("span");
    preview.className = "conversation-preview";
    preview.textContent = conversation.preview || t("conversations.no_messages");
    description.append(title, preview);
    const state = conversationState(conversation);
    const status = document.createElement("span");
    status.className = `status-chip ${state.className}`;
    status.textContent = state.label;
    const updated = document.createElement("span");
    updated.className = "conversation-date";
    updated.textContent = formatDate(conversation.updated_at);
    open.append(description, status, updated);
    row.append(
      open,
      deleteButton(t("conversations.delete_aria", { title: conversation.title }), () =>
        requestDelete("conversation", conversation.id, conversation.title)),
    );
    conversationList.append(row);
  });
}

async function loadConversations() {
  conversationList.innerHTML = '<div class="loading-state" aria-label="Loading conversations"><span></span><span></span></div>';
  try {
    renderConversations(await api("/api/conversations"));
  } catch (error) {
    conversationList.textContent = error.message;
  }
}

function fillContextForm(context, status = "draft") {
  contextFields.forEach((name) => {
    const field = contextForm.elements.namedItem(name);
    const value = context[name];
    field.value = listFields.has(name) ? (value || []).join("\n") : (value || "");
  });
  reviewState.textContent = status === "approved" ? t("review.state_approved") : t("review.state_draft");
  reviewState.classList.toggle("approved", status === "approved");
  reviewTitle.textContent = context.name ? t("review.title_named", { name: context.name }) : t("review.title_default");
  setStatus(reviewStatus, "");
  loadApprovalDocuments();
}

async function loadApprovalDocuments() {
  approvalDocumentsList.replaceChildren();
  if (!currentContextId) {
    approvalDocumentsSection.hidden = true;
    return;
  }
  try {
    const uploads = (await api("/api/uploads")).filter(
      (upload) => upload.kind === "context_evidence" && upload.context_id === currentContextId,
    );
    approvalDocumentsSection.hidden = !uploads.length;
    uploads.forEach((upload) => {
      const label = document.createElement("label");
      label.className = "approval-document";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.value = upload.id;
      checkbox.checked = upload.visibility === "org" || upload.visibility === "private";
      const copy = document.createElement("span");
      copy.textContent = upload.filename;
      label.append(checkbox, copy);
      approvalDocumentsList.append(label);
    });
  } catch (error) {
    approvalDocumentsSection.hidden = true;
  }
}

function readContextForm() {
  return Object.fromEntries(
    contextFields.map((name) => {
      const field = contextForm.elements.namedItem(name);
      const value = listFields.has(name)
        ? field.value.split("\n").map((item) => item.trim()).filter(Boolean)
        : field.value.trim();
      return [name, value];
    }),
  );
}

async function saveConversationContext() {
  if (!currentConversation?.is_ready_to_save || currentConversation.portfolio_context_id) return;
  saveToPortfolio.disabled = true;
  saveToPortfolio.textContent = t("builder.preparing");
  setStatus(chatStatus, t("builder.saving_status"), "success");
  try {
    const context = await api(`/api/conversations/${currentConversation.id}/portfolio`, { method: "POST" });
    currentContextId = context.id;
    currentConversation.portfolio_context_id = context.id;
    reviewOrigin = "builder";
    backFromReview.textContent = t("review.back");
    fillContextForm(context, context.status);
    renderConversation(currentConversation);
    showView("review");
  } catch (error) {
    setStatus(chatStatus, error.message);
    saveToPortfolio.disabled = false;
    saveToPortfolio.textContent = t("builder.save_to_portfolio");
  }
}

async function saveContext(status) {
  if (!contextForm.reportValidity()) return;
  const buttons = [saveDraftButton, approveContextButton];
  buttons.forEach((button) => { button.disabled = true; });
  setStatus(reviewStatus, status === "approved" ? t("review.approving") : t("review.saving"), "success");
  try {
    const path = currentContextId ? `/api/contexts/${currentContextId}` : "/api/contexts";
    const publishUploadIds = status === "approved"
      ? [...approvalDocumentsList.querySelectorAll('input[type="checkbox"]:checked')].map((item) => item.value)
      : [];
    const saved = await api(path, {
      method: currentContextId ? "PUT" : "POST",
      body: JSON.stringify({ context: readContextForm(), status, publish_upload_ids: publishUploadIds }),
    });
    currentContextId = saved.id;
    fillContextForm(saved, saved.status);
    setStatus(reviewStatus, saved.status === "approved" ? t("review.approved_status") : t("review.saved_status"), "success");
    await loadPortfolio();
    showView("portfolio");
  } catch (error) {
    setStatus(reviewStatus, error.message);
  } finally {
    buttons.forEach((button) => { button.disabled = false; });
  }
}

function portfolioItems() {
  return [
    ...portfolioContexts.map((context) => ({
      ...context,
      kind: "context",
      origin: "SIP",
    })),
    ...portfolioSources.map((source) => ({
      ...source,
      kind: "website",
      status: "website",
      origin: source.organisation,
    })),
  ];
}

function populatePortfolioFilters(items) {
  const origins = [...new Set(items.map((item) => item.origin))].sort();
  const selected = portfolioFilterOrigin.value;
  portfolioFilterOrigin.replaceChildren();
  const allOption = document.createElement("option");
  allOption.value = "";
  allOption.textContent = t("portfolio.filter_origin_all");
  portfolioFilterOrigin.append(allOption);
  origins.forEach((origin) => {
    const option = document.createElement("option");
    option.value = origin;
    option.textContent = origin;
    portfolioFilterOrigin.append(option);
  });
  if (origins.includes(selected)) portfolioFilterOrigin.value = selected;
}

function renderPortfolio() {
  const items = portfolioItems();
  populatePortfolioFilters(items);
  const query = portfolioSearch.value.trim().toLowerCase();
  const typeFilter = portfolioFilterType.value;
  const originFilter = portfolioFilterOrigin.value;
  const visibleItems = items.filter((item) => {
    const matchesQuery = `${item.name} ${item.short_summary} ${item.origin}`.toLowerCase().includes(query);
    return matchesQuery
      && (!typeFilter || item.offering_type === typeFilter)
      && (!originFilter || item.origin === originFilter);
  }).sort((left, right) => left.name.localeCompare(right.name));
  portfolioList.replaceChildren();
  portfolioCount.textContent = visibleItems.length === 1
    ? t("portfolio.count_one")
    : t("portfolio.count_other", { count: visibleItems.length });
  const hasFilter = Boolean(query || typeFilter || originFilter);
  if (!visibleItems.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    const title = document.createElement("h2");
    title.textContent = hasFilter ? t("portfolio.empty_title_query") : t("portfolio.empty_title_default");
    const copy = document.createElement("p");
    copy.textContent = hasFilter ? t("portfolio.empty_copy_query") : t("portfolio.empty_copy_default");
    empty.append(title, copy);
    portfolioList.append(empty);
    return;
  }
  visibleItems.forEach((item) => {
    const row = document.createElement("div");
    row.className = "portfolio-row";
    const open = document.createElement("button");
    open.type = "button";
    open.className = "row-open";
    open.addEventListener("click", () => item.kind === "context" ? openContext(item.id) : openSource(item.id));
    const description = document.createElement("span");
    const title = document.createElement("span");
    title.className = "portfolio-title";
    title.textContent = item.name || t("portfolio.untitled");
    const typeTag = document.createElement("span");
    typeTag.className = "portfolio-type-tag";
    typeTag.textContent = item.offering_type === "service" ? t("review.field.type_service") : t("review.field.type_product");
    title.append(" ", typeTag);
    const summary = document.createElement("span");
    summary.className = "portfolio-summary";
    summary.textContent = item.short_summary || t("portfolio.no_summary");
    description.append(title, summary);
    const status = document.createElement("span");
    status.className = `status-chip ${item.status}`;
    status.textContent = t(`status.${item.status}`);
    const origin = document.createElement("span");
    origin.className = "portfolio-date";
    origin.textContent = item.origin;
    open.append(description, status, origin);
    row.append(open);
    if (item.kind === "context" && currentRole !== "sales") {
      row.append(
        deleteButton(t("portfolio.delete_aria", { name: item.name || t("portfolio.untitled") }), () =>
          requestDelete("context", item.id, item.name || t("portfolio.untitled"))),
      );
    } else {
      row.classList.add("read-only");
    }
    portfolioList.append(row);
  });
}

async function loadPortfolio() {
  portfolioList.innerHTML = '<div class="loading-state" aria-label="Loading portfolio"><span></span><span></span></div>';
  try {
    const [solutionResponse, serviceResponse, productResponse] = await Promise.all([
      api("/api/portfolio/solutions"),
      api("/api/portfolio/sources?page_type=service&limit=100"),
      api("/api/portfolio/sources?page_type=solution&limit=100"),
    ]);
    portfolioContexts = solutionResponse.items;
    portfolioSources = [...serviceResponse.items, ...productResponse.items];
    renderPortfolio();
  } catch (error) {
    portfolioList.textContent = error.message;
  }
}

function createEmptyFieldNote() {
  const note = document.createElement("span");
  note.className = "empty-field";
  note.textContent = t("source.field_empty");
  return note;
}

function renderTextList(container, values) {
  container.replaceChildren();
  if (!values || !values.length) {
    container.append(createEmptyFieldNote());
    return;
  }
  const list = document.createElement("ul");
  list.className = "read-only-list";
  values.forEach((value) => {
    const item = document.createElement("li");
    item.textContent = value;
    list.append(item);
  });
  container.append(list);
}

function renderTextField(container, value) {
  container.replaceChildren();
  container.append(value ? document.createTextNode(value) : createEmptyFieldNote());
}

function renderSourceContent(source) {
  sourceContent.replaceChildren();
  if (source.details.length) {
    sourceContent.append(createSourceSection(t("source.details"), "", source.details));
  }
  source.sections.forEach((section) => {
    sourceContent.append(createSourceSection(section.title, section.introduction, section.items));
  });
}

function createSourceSection(title, introduction, items) {
  const section = document.createElement("section");
  section.className = "form-section";
  const heading = document.createElement("h2");
  heading.textContent = title;
  const grid = document.createElement("div");
  grid.className = "form-grid";
  if (introduction) {
    const field = document.createElement("div");
    field.className = "field full-width";
    const value = document.createElement("div");
    value.className = "read-only-field multiline";
    value.textContent = introduction;
    field.append(value);
    grid.append(field);
  }
  // Items that carry a description are shown as labelled fields. Items without one
  // are not broken data: on the source websites they are logo tiles and contact
  // cards that genuinely have no prose. Showing a placeholder sentence under each
  // made the page look defective, so they render as a plain list of names instead.
  items
    .filter((item) => item.value)
    .forEach((item) => {
      const field = document.createElement("div");
      field.className = "field";
      const label = document.createElement("span");
      label.textContent = item.label;
      const value = document.createElement("div");
      value.className = "read-only-field multiline";
      value.textContent = item.value;
      field.append(label, value);
      grid.append(field);
    });
  const labelOnlyItems = items.filter((item) => !item.value);
  if (labelOnlyItems.length) {
    const field = document.createElement("div");
    field.className = "field full-width";
    const list = document.createElement("ul");
    list.className = "label-chips";
    labelOnlyItems.forEach((item) => {
      const chip = document.createElement("li");
      chip.textContent = item.label;
      list.append(chip);
    });
    field.append(list);
    grid.append(field);
  }
  section.append(heading, grid);
  return section;
}

async function openSource(sourceId) {
  sourceContent.innerHTML = '<div class="loading-state" aria-label="Loading source"><span></span><span></span></div>';
  showView("source");
  try {
    const source = await api(`/api/portfolio/sources/${encodeURIComponent(sourceId)}`);
    sourceTitle.textContent = t("source.title_named", { name: source.name });
    sourceOrigin.textContent = new URL(source.url).hostname;
    sourceName.textContent = source.name;
    sourceSummary.textContent = source.short_summary;
    sourceOrganisation.textContent = source.organisation;
    sourceLanguage.textContent = source.language.toUpperCase();
    sourceType.textContent = source.offering_type
      ? (source.offering_type === "service" ? t("review.field.type_service") : t("review.field.type_product"))
      : "";
    renderTextField(sourceType, sourceType.textContent);
    sourcePageType.textContent = source.page_type.replaceAll("_", " ");
    // Every field is rendered whether or not the page supplied it. An empty field
    // is information: it tells a Product Owner the website does not state this.
    sourceProblemsField.hidden = false;
    sourceCapabilitiesField.hidden = false;
    renderTextList(sourceProblems, source.customer_problems_addressed);
    renderTextList(sourceCapabilities, source.core_capabilities);
    renderTextField(sourceValue, source.value_proposition);
    renderTextList(sourceDifferentiators, source.differentiators);
    renderTextList(sourcePeople, source.people);
    renderTextList(sourceTargetOrganisations, source.target_organisations);
    renderTextList(sourceRelevantIndustries, source.relevant_industries);
    renderTextList(sourceRelevantRoles, source.relevant_roles_and_decision_makers);
    renderTextList(sourceGeographicFocus, source.geographic_focus);
    renderTextList(sourceEvidence, source.supporting_evidence_or_knowledge_sources);
    renderTextList(sourceMarketingMessages, source.key_marketing_messages);
    renderTextList(sourceAssumptions, source.assumptions);
    renderTextList(sourceOpenQuestions, source.open_questions);
    sourceOpenOriginal.href = source.url;
    sourceOriginal.hidden = !source.sections.length && !source.details.length;
    renderSourceContent(source);
  } catch (error) {
    sourceTitle.textContent = t("source.error_title");
    sourceContent.textContent = error.message;
  }
}

function appendKnowledgeMessage(text, role, sources = [], nearMisses = []) {
  const row = appendMessage(knowledgeMessages, text, role, t("knowledge.assistant_name"));
  if (role === "assistant" && sources.length) {
    const links = document.createElement("div");
    links.className = "message-sources";
    sources.forEach((source, index) => {
      const link = document.createElement("a");
      link.href = source.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = `[${index + 1}] ${source.title}`;
      links.append(link);
    });
    row.querySelector(".message-content").append(links);
  }
  if (role === "assistant" && nearMisses.length) {
    const block = document.createElement("div");
    block.className = "near-misses";
    const label = document.createElement("strong");
    label.textContent = t("knowledge.near_misses");
    block.append(label);
    nearMisses.forEach((source) => {
      const link = document.createElement("a");
      link.href = source.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = `${source.title} (${source.score.toFixed(4)})`;
      block.append(link);
    });
    row.querySelector(".message-content").append(block);
  }
  return row;
}

function resetKnowledgeChat() {
  knowledgeConversationId = null;
  knowledgeMessages.replaceChildren();
  appendKnowledgeMessage(t("knowledge.first_message"), "assistant");
  setStatus(knowledgeStatus, "");
  knowledgeInput.value = "";
  resizeTextArea(knowledgeInput);
}

function showKnowledgeHome() {
  knowledgeConversationId = null;
  knowledgeHome.hidden = false;
  knowledgeChat.hidden = true;
  document.body.classList.remove("chat-open");
  knowledgeStartMessage.value = "";
  knowledgeStartMessage.focus();
}

function showKnowledgeConversation() {
  knowledgeHome.hidden = true;
  knowledgeChat.hidden = false;
  document.body.classList.add("chat-open");
}

async function openKnowledgeConversation(conversationId) {
  const conversation = await api(`/api/conversations/${conversationId}`);
  knowledgeConversationId = conversation.id;
  knowledgeMessages.replaceChildren();
  if (!conversation.messages.length) appendKnowledgeMessage(t("knowledge.first_message"), "assistant");
  else conversation.messages.forEach((message) => appendKnowledgeMessage(message.content, message.role));
  knowledgeHistory.value = conversation.id;
  showKnowledgeConversation();
  knowledgeInput.focus();
}

async function uploadDocument(file, kind, conversationId = null) {
  const form = new FormData();
  form.append("file", file);
  form.append("kind", kind);
  if (conversationId) form.append("conversation_id", conversationId);
  return api("/api/uploads", { method: "POST", body: form });
}

function renderDocumentProposals(upload, proposals) {
  if (!proposals.length) return addMessage(t("uploads.no_proposals"), "assistant");
  const row = addMessage(t("uploads.proposals_intro", { filename: upload.filename }), "assistant");
  const container = document.createElement("div");
  container.className = "proposal-list";
  proposals.forEach((proposal) => {
    const card = document.createElement("div");
    card.className = "proposal-card";
    const provenance = document.createElement("small");
    provenance.textContent = `${upload.filename}${proposal.page ? ` · p. ${proposal.page}` : ""}: “${proposal.quote}”`;
    const field = document.createElement("strong");
    field.textContent = proposal.field_name.replaceAll("_", " ");
    const value = document.createElement("input");
    value.value = proposal.value;
    const actions = document.createElement("div");
    actions.className = "proposal-actions";
    const accept = document.createElement("button");
    accept.type = "button";
    accept.className = "secondary-button";
    accept.textContent = t("uploads.accept");
    const ignore = document.createElement("button");
    ignore.type = "button";
    ignore.className = "text-button";
    ignore.textContent = t("uploads.ignore");
    accept.addEventListener("click", () => {
      acceptedDocumentProposals.push({ ...proposal, value: value.value.trim() });
      card.remove();
    });
    ignore.addEventListener("click", () => card.remove());
    actions.append(accept, ignore);
    card.append(provenance, field, value, actions);
    container.append(card);
  });
  row.querySelector(".message-content").append(container);
}

contextUpload.addEventListener("change", async () => {
  const file = contextUpload.files[0];
  if (!file || !currentConversation) return;
  setStatus(chatStatus, t("uploads.processing"), "success");
  try {
    const upload = await uploadDocument(file, "context_evidence", currentConversation.id);
    const batch = await api(`/api/uploads/${upload.id}/proposals`, { method: "POST" });
    renderDocumentProposals(upload, batch.proposals);
    setStatus(chatStatus, t("uploads.private_evidence"), "success");
  } catch (error) {
    setStatus(chatStatus, error.message);
  } finally {
    contextUpload.value = "";
  }
});

knowledgeUpload.addEventListener("change", async () => {
  const file = knowledgeUpload.files[0];
  if (!file) return;
  setStatus(knowledgeStatus, t("uploads.processing"), "success");
  try {
    const upload = await uploadDocument(file, "workspace");
    appendKnowledgeMessage(t("uploads.added", { filename: upload.filename }), "assistant");
    setStatus(knowledgeStatus, t("uploads.private_workspace"), "success");
  } catch (error) {
    setStatus(knowledgeStatus, error.message);
  } finally {
    knowledgeUpload.value = "";
  }
});

async function loadKnowledgeHistory() {
  const conversations = await api("/api/conversations?kind=knowledge");
  knowledgeHistory.replaceChildren(new Option(t("knowledge.history"), ""));
  knowledgeConversationList.replaceChildren();
  conversations.forEach((conversation) => {
    knowledgeHistory.add(new Option(conversation.title, conversation.id));
    const row = document.createElement("div");
    row.className = "conversation-row";
    const open = document.createElement("button");
    open.type = "button";
    open.className = "row-open";
    open.addEventListener("click", () => openKnowledgeConversation(conversation.id));
    const description = document.createElement("span");
    const title = document.createElement("span");
    title.className = "conversation-title";
    title.textContent = conversation.title;
    const preview = document.createElement("span");
    preview.className = "conversation-preview";
    preview.textContent = conversation.preview || t("conversations.no_messages");
    description.append(title, preview);
    const spacer = document.createElement("span");
    const updated = document.createElement("span");
    updated.className = "conversation-date";
    updated.textContent = formatDate(conversation.updated_at);
    open.append(description, spacer, updated);
    row.append(open, deleteButton(t("conversations.delete_aria", { title: conversation.title }), () =>
      requestDelete("conversation", conversation.id, conversation.title)));
    knowledgeConversationList.append(row);
  });
  if (!conversations.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = t("conversations.empty_title");
    knowledgeConversationList.append(empty);
  }
  acceptedDocumentProposals.forEach(({ field_name, value }) => {
    const field = contextForm.elements.namedItem(field_name);
    if (!field || field_name === "assumptions" || field_name === "open_questions") return;
    if (listFields.has(field_name)) {
      const values = field.value.split("\n").filter(Boolean);
      if (!values.includes(value)) field.value = [...values, value].join("\n");
    } else if (!field.value) field.value = value;
  });
  knowledgeHistory.value = knowledgeConversationId || "";
}

knowledgeHistory.addEventListener("change", async () => {
  if (!knowledgeHistory.value) return resetKnowledgeChat();
  await openKnowledgeConversation(knowledgeHistory.value);
});

knowledgeStartForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = knowledgeStartMessage.value.trim();
  if (!message) return;
  knowledgeStartSend.disabled = true;
  resetKnowledgeChat();
  knowledgeInput.value = message;
  showKnowledgeConversation();
  knowledgeChatForm.requestSubmit();
  knowledgeStartSend.disabled = false;
});

conversationStartMessage.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    conversationStartForm.requestSubmit();
  }
});

knowledgeStartMessage.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    knowledgeStartForm.requestSubmit();
  }
});

function renderTeam(users) {
  teamList.replaceChildren();
  if (!users.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    const copy = document.createElement("p");
    copy.textContent = t("team.empty");
    empty.append(copy);
    teamList.append(empty);
    return;
  }
  users.forEach((user) => {
    const row = document.createElement("div");
    row.className = "team-row";

    const emailCell = document.createElement("span");
    emailCell.className = "team-email";
    emailCell.textContent = user.email;
    if (user.email === currentUserEmail) {
      const youTag = document.createElement("span");
      youTag.className = "team-you-tag";
      youTag.textContent = t("team.you");
      emailCell.append(" ", youTag);
    }

    const roleSelect = document.createElement("select");
    ["admin", "product_owner", "sales"].forEach((role) => {
      const option = document.createElement("option");
      option.value = role;
      option.textContent = t(`role.${role}`);
      if (role === user.role) option.selected = true;
      roleSelect.append(option);
    });
    roleSelect.addEventListener("change", async () => {
      roleSelect.disabled = true;
      try {
        await api(`/api/users/${user.id}`, {
          method: "PUT",
          body: JSON.stringify({ role: roleSelect.value }),
        });
        setStatus(teamStatus, t("team.role_updated"), "success");
      } catch (error) {
        setStatus(teamStatus, error.message);
        roleSelect.value = user.role;
      } finally {
        roleSelect.disabled = false;
      }
    });

    const added = document.createElement("span");
    added.className = "conversation-date";
    added.textContent = formatDate(user.created_at);

    const isSelf = user.email === currentUserEmail;
    const remove = deleteButton(t("portfolio.delete_aria", { name: user.email }), async () => {
      if (isSelf) {
        setStatus(teamStatus, t("team.cannot_delete_self"));
        return;
      }
      if (!window.confirm(t("team.delete_confirm", { email: user.email }))) return;
      try {
        await api(`/api/users/${user.id}`, { method: "DELETE" });
        setStatus(teamStatus, t("team.deleted"), "success");
        await loadTeam();
      } catch (error) {
        setStatus(teamStatus, error.message);
      }
    });
    if (isSelf) remove.disabled = true;

    row.append(emailCell, roleSelect, added, remove);
    teamList.append(row);
  });
}

async function loadTeam() {
  teamList.innerHTML = '<div class="loading-state" aria-label="Loading team"><span></span><span></span></div>';
  try {
    renderTeam(await api("/api/users"));
  } catch (error) {
    teamList.textContent = error.message;
  }
}

async function openContext(contextId) {
  try {
    const context = await api(`/api/contexts/${contextId}`);
    currentContextId = context.id;
    reviewOrigin = "portfolio";
    backFromReview.textContent = t("review.back_portfolio");
    fillContextForm(context, context.status);
    showView("review");
  } catch (error) {
    portfolioList.textContent = error.message;
  }
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message || !currentConversation) return;
  const userRow = addMessage(message, "user");
  input.value = "";
  resizeTextArea(input);
  send.disabled = true;
  setStatus(chatStatus, t("builder.thinking"), "success");
  try {
    const data = await api(`/api/conversations/${currentConversation.id}/messages`, {
      method: "POST",
      body: JSON.stringify({ message }),
    });
    currentConversation = data.conversation;
    renderConversation(currentConversation);
  } catch (error) {
    userRow.remove();
    input.value = message;
    resizeTextArea(input);
    setStatus(chatStatus, error instanceof TypeError ? t("builder.unreachable") : error.message);
  } finally {
    send.disabled = false;
    input.focus();
  }
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});
input.addEventListener("input", () => resizeTextArea(input));
saveToPortfolio.addEventListener("click", saveConversationContext);
newConversationButton.addEventListener("click", createConversation);
document.querySelector("#back-to-conversations").addEventListener("click", async () => {
  await loadConversations();
  showView("conversations");
});
saveDraftButton.addEventListener("click", () => saveContext("draft"));
approveContextButton.addEventListener("click", () => saveContext("approved"));
portfolioCreate.addEventListener("click", createConversation);
portfolioSearch.addEventListener("input", renderPortfolio);
portfolioFilterType.addEventListener("change", renderPortfolio);
portfolioFilterOrigin.addEventListener("change", renderPortfolio);
document.querySelector("#back-to-sources").addEventListener("click", () => {
  showView("portfolio");
});
backFromReview.addEventListener("click", () => showView(reviewOrigin));

knowledgeChatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = knowledgeInput.value.trim();
  if (!message) return;
  const userRow = appendKnowledgeMessage(message, "user");
  knowledgeInput.value = "";
  resizeTextArea(knowledgeInput);
  knowledgeSend.disabled = true;
  setStatus(knowledgeStatus, t("knowledge.thinking"), "success");
  try {
    const data = await api("/api/knowledge/chat", {
      method: "POST",
      body: JSON.stringify({
        message,
        conversation_id: knowledgeConversationId,
        language: getLanguage(),
      }),
    });
    knowledgeConversationId = data.conversation_id;
    appendKnowledgeMessage(
      data.message,
      "assistant",
      data.sources,
      data.near_misses,
    );
    await loadKnowledgeHistory();
    setStatus(knowledgeStatus, "");
  } catch (error) {
    userRow.remove();
    knowledgeInput.value = message;
    resizeTextArea(knowledgeInput);
    setStatus(knowledgeStatus, error instanceof TypeError ? t("builder.unreachable") : error.message);
  } finally {
    knowledgeSend.disabled = false;
    knowledgeInput.focus();
  }
});

knowledgeInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    knowledgeChatForm.requestSubmit();
  }
});
knowledgeInput.addEventListener("input", () => resizeTextArea(knowledgeInput));
newKnowledgeChat.addEventListener("click", () => {
  showKnowledgeHome();
  loadKnowledgeHistory();
});

languageSwitcher.addEventListener("change", () => {
  setLanguage(languageSwitcher.value);
  if (currentRole) roleBadge.textContent = t(`role.${currentRole}`);
  if (!views.conversations.hidden) loadConversations();
  if (!views.portfolio.hidden) {
    renderPortfolio();
  }
  if (!views.knowledge.hidden && !knowledgeConversationId) resetKnowledgeChat();
});

document.querySelectorAll(".nav-item[data-view]").forEach((item) => {
  item.addEventListener("click", async () => {
    if (item.dataset.view === "conversations") await loadConversations();
    if (item.dataset.view === "portfolio") await loadPortfolio();
    if (item.dataset.view === "team") await loadTeam();
    showView(item.dataset.view);
    if (item.dataset.view === "knowledge") {
      await loadKnowledgeHistory();
      showKnowledgeHome();
    }
  });
});

createUserForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitButton = createUserForm.querySelector('button[type="submit"]');
  submitButton.disabled = true;
  setStatus(teamStatus, t("team.creating"), "success");
  try {
    await api("/api/users", {
      method: "POST",
      body: JSON.stringify({
        email: createUserForm.elements.email.value.trim(),
        password: createUserForm.elements.password.value,
        role: createUserForm.elements.role.value,
      }),
    });
    createUserForm.reset();
    setStatus(teamStatus, t("team.created"), "success");
    await loadTeam();
  } catch (error) {
    setStatus(teamStatus, error.message.includes("already exists") ? t("team.email_taken") : error.message);
  } finally {
    submitButton.disabled = false;
  }
});

document.querySelectorAll("[data-return='portfolio']").forEach((button) => {
  button.addEventListener("click", async () => {
    await loadPortfolio();
    showView("portfolio");
  });
});

confirmDelete.addEventListener("click", async () => {
  if (!pendingDelete) return;
  confirmDelete.disabled = true;
  const { kind, id } = pendingDelete;
  try {
    await api(kind === "conversation" ? `/api/conversations/${id}` : `/api/contexts/${id}`, {
      method: "DELETE",
    });
    deleteDialog.close();
    pendingDelete = null;
    if (kind === "conversation") {
      await loadConversations();
      if (!views.knowledge.hidden) await loadKnowledgeHistory();
    }
    else await loadPortfolio();
  } catch (error) {
    deleteDescription.textContent = error.message;
  } finally {
    confirmDelete.disabled = false;
  }
});

deleteDialog.addEventListener("close", () => {
  pendingDelete = null;
});

applyTranslations();
resetKnowledgeChat();
loadCurrentUser();
loadConversations();
