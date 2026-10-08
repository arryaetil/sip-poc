const views = {
  home: document.querySelector("#home-view"),
  conversations: document.querySelector("#conversations-view"),
  builder: document.querySelector("#builder-view"),
  review: document.querySelector("#review-view"),
  portfolio: document.querySelector("#portfolio-view"),
  source: document.querySelector("#source-view"),
  knowledge: document.querySelector("#knowledge-view"),
  "product-owner": document.querySelector("#product-owner-view"),
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
const poHome = document.querySelector("#po-home");
const poChat = document.querySelector("#po-chat");
const poMessages = document.querySelector("#po-messages");
const poChatForm = document.querySelector("#po-chat-form");
const poInput = document.querySelector("#po-message");
const poSend = document.querySelector("#po-send");
const poStatus = document.querySelector("#po-status");
const poHistory = document.querySelector("#po-history");
const poConversationList = document.querySelector("#po-conversation-list");
const poStartForm = document.querySelector("#po-start-form");
const poStartMessage = document.querySelector("#po-start-message");
const poStartSend = document.querySelector("#po-start-send");
const newPoChat = document.querySelector("#new-po-chat");
const navProductOwner = document.querySelector("#nav-product-owner");
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
// Set while the review page shows changes proposed by an update conversation.
let pendingUpdate = null;
let updatableContexts = [];
const conversationTarget = document.querySelector("#conversation-target");
const conversationTargetField = document.querySelector("#conversation-target-field");
const reviewChanges = document.querySelector("#review-changes");
const reviewChangesList = document.querySelector("#review-changes-list");

// Field names of a Business Context, as the review form labels them.
const CONTEXT_FIELD_LABELS = {
  status: "history.field.status",
  name: "review.field.name",
  offering_type: "review.field.type",
  short_summary: "review.field.short_summary",
  customer_problems_addressed: "review.field.customer_problems",
  core_capabilities: "review.field.core_capabilities",
  target_organisations: "review.field.target_organisations",
  relevant_industries: "review.field.relevant_industries",
  relevant_roles_and_decision_makers: "review.field.relevant_roles",
  geographic_focus: "review.field.geographic_focus",
  value_proposition: "review.field.value_proposition",
  differentiators: "review.field.differentiators",
  people: "review.field.people",
  supporting_evidence_or_knowledge_sources: "review.field.evidence_sources",
  key_marketing_messages: "review.field.key_marketing_messages",
  assumptions: "review.field.assumptions",
  open_questions: "review.field.open_questions",
};

function contextFieldLabel(field) {
  return CONTEXT_FIELD_LABELS[field] ? t(CONTEXT_FIELD_LABELS[field]) : field;
}

// What changed per field: removed lines, added lines, or old and new text.
function renderContextChanges(changes, container) {
  container.replaceChildren();
  if (!changes.length) {
    const none = document.createElement("p");
    none.className = "context-changes-none";
    none.textContent = t("review.changes_none");
    container.append(none);
    return;
  }
  changes.forEach((change) => {
    const block = document.createElement("div");
    block.className = "context-change";
    const label = document.createElement("h3");
    label.textContent = contextFieldLabel(change.field);
    block.append(label);
    const lines = change.kind === "list"
      ? [...change.removed.map((text) => ["removed", text]), ...change.added.map((text) => ["added", text])]
      : [["removed", change.before], ["added", change.after]].filter(([, text]) => text);
    lines.forEach(([kind, text]) => {
      const line = document.createElement("p");
      line.className = `context-change-line is-${kind}`;
      const mark = document.createElement("span");
      mark.className = "context-change-mark";
      mark.setAttribute("aria-label", t(kind === "added" ? "history.added" : "history.removed"));
      mark.textContent = kind === "added" ? "+" : "−";
      line.append(mark, document.createTextNode(text));
      block.append(line);
    });
    container.append(block);
  });
}
let currentUserEmail = "";

async function api(path, options = {}) {
  const isFormData = options.body instanceof FormData;
  const response = await fetch(path, {
    ...options,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      // The server answers error messages in this language.
      "X-SIP-Language": getLanguage(),
      ...(options.headers || {}),
    },
  });
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : t("error.request_failed"));
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
  try {
    const { available } = await api("/api/developer/availability");
    document.querySelector("[data-developer-open]").dataset.available = String(available);
  } catch {
    document.querySelector("[data-developer-open]").dataset.available = "false";
  }
  applySpecialistAvailability();
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

  // Mirrors _role_allows: Sales has no access to the Product Owner, and the
  // Lead finder is for sales and admin only.
  navProductOwner.hidden = currentRole === "sales";
  document.querySelector("#nav-lead").hidden = !["admin", "sales"].includes(currentRole);

  const isAdmin = currentRole === "admin";
  navTeam.hidden = !isAdmin;
  navLabelAdministration.hidden = !isAdmin;
  applySpecialistAvailability();
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

const SIDEBAR_KEY = "sip:sidebar-collapsed";
const sidebarToggle = document.querySelector("#sidebar-toggle");

function syncSidebarLabels() {
  const collapsed = document.body.classList.contains("sidebar-collapsed");
  sidebarToggle.setAttribute("aria-expanded", String(!collapsed));
  sidebarToggle.setAttribute("aria-label", t(collapsed ? "nav.expand" : "nav.collapse"));
  sidebarToggle.title = t(collapsed ? "nav.expand" : "nav.collapse");
  // Collapsed, only icons show: the name becomes the tooltip.
  document.querySelectorAll(".sidebar .nav-item").forEach((item) => {
    const label = item.querySelector("span")?.textContent.trim() || "";
    if (collapsed) item.title = label;
    else item.removeAttribute("title");
  });
}

function setSidebarCollapsed(collapsed) {
  document.body.classList.toggle("sidebar-collapsed", collapsed);
  try { localStorage.setItem(SIDEBAR_KEY, collapsed ? "1" : "0"); } catch {}
  syncSidebarLabels();
}

sidebarToggle.addEventListener("click", () =>
  setSidebarCollapsed(!document.body.classList.contains("sidebar-collapsed")));
try { if (localStorage.getItem(SIDEBAR_KEY) === "1") document.body.classList.add("sidebar-collapsed"); } catch {}
document.querySelector("#language-switcher")?.addEventListener("change", () => setTimeout(syncSidebarLabels));
setTimeout(syncSidebarLabels);

function showView(name) {
  Object.entries(views).forEach(([viewName, element]) => {
    element.hidden = viewName !== name;
  });
  document.body.classList.toggle(
    "chat-open",
    name === "builder" || name === "marketing"
      || (name === "knowledge" && !knowledgeChat.hidden)
      || (name === "product-owner" && !poChat.hidden),
  );
  // Home is the start screen: the specialists are the navigation, so no sidebar.
  document.body.classList.toggle("home-open", name === "home");
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
  syncHomeMedia();
}

function resizeTextArea(textarea) {
  textarea.style.height = "auto";
  textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`;
  // A scrollbar only once the text is taller than the box may grow.
  textarea.style.overflowY = textarea.scrollHeight > 180 ? "auto" : "hidden";
}

function revealMessage(message, text, container) {
  // The Product Owner chat places its answer once and does not chase the typing.
  const follow = container !== poMessages;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    message.textContent = text;
    return;
  }
  // Screen readers get the whole answer once; the typing copy is hidden from them,
  // otherwise every few words would be announced again.
  message.setAttribute("aria-hidden", "true");
  const spoken = document.createElement("span");
  spoken.className = "visually-hidden";
  spoken.textContent = text;
  message.after(spoken);
  const tokens = text.match(/\S+\s*/g) || [text];
  const batchSize = Math.max(1, Math.ceil(tokens.length / 120));
  let index = 0;
  message.textContent = "";
  message.classList.add("typing");
  const step = () => {
    message.textContent += tokens.slice(index, index + batchSize).join("");
    index += batchSize;
    if (follow) container.scrollTop = container.scrollHeight;
    if (index < tokens.length) window.setTimeout(step, 22);
    else message.classList.remove("typing");
  };
  window.setTimeout(step, 80);
}

// Each chat shows the robot of its specialist from the home page.
function chatAvatarFor(container) {
  if (container.id === "lead-messages") return "lead-finder";
  return container === poMessages ? "product-owner" : "kennis";
}

function robotAvatar(name) {
  const avatar = document.createElement("span");
  avatar.className = "avatar avatar-robot";
  avatar.setAttribute("aria-hidden", "true");
  const image = document.createElement("img");
  image.src = `/avatars/${name}.webp`;
  image.alt = "";
  image.decoding = "async";
  avatar.append(image);
  return avatar;
}

function appendMessage(container, text, role, assistantName, animate = false) {
  const row = document.createElement("div");
  row.className = `message-row ${role}`;
  if (role === "assistant") row.append(robotAvatar(chatAvatarFor(container)));
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
  if (animate && role === "assistant") revealMessage(message, text, container);
  else message.textContent = text;
  content.append(message);
  row.append(content);
  container.append(row);
  container.scrollTop = container.scrollHeight;
  return row;
}

function addMessage(text, role, animate = false) {
  return appendMessage(messages, text, role, t("assistant.name"), animate);
}

function renderConversation(conversation, animateLatest = false) {
  currentConversation = conversation;
  builderTitle.textContent = conversation.title;
  messages.replaceChildren();
  if (!conversation.messages.length) {
    addMessage(t("assistant.first_message"), "assistant");
  } else {
    conversation.messages.forEach((message, index) => addMessage(
      message.content,
      message.role,
      animateLatest && index === conversation.messages.length - 1 && message.role === "assistant",
    ));
  }

  const isSaved = Boolean(conversation.portfolio_context_id);
  const isUpdate = Boolean(conversation.updates_context_id);
  readiness.hidden = !conversation.is_ready_to_save && !isSaved;
  readiness.dataset.ready = String(conversation.is_ready_to_save && !isSaved);
  const actionLabel = isUpdate ? t("builder.review_changes") : t("builder.save_to_portfolio");
  if (isSaved) {
    readinessText.textContent = isUpdate ? t("builder.changes_saved_note") : t("builder.saved_note");
    saveToPortfolio.textContent = isUpdate ? t("builder.changes_saved") : t("builder.saved_to_portfolio");
    saveToPortfolio.disabled = true;
  } else if (conversation.is_ready_to_save) {
    readinessText.textContent = conversation.readiness_reason || t("builder.ready_note_default");
    saveToPortfolio.textContent = actionLabel;
    saveToPortfolio.disabled = false;
  } else {
    readinessText.textContent = conversation.readiness_reason || t("builder.not_ready_default");
    saveToPortfolio.textContent = actionLabel;
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
  const target = updatableContexts.find((item) => item.id === conversationTarget.value);
  if (target) builderTitle.textContent = t("builder.updating", { name: target.name });
  try {
    const conversation = await api("/api/conversations", {
      method: "POST",
      body: JSON.stringify({ language: getLanguage(), kind: "context", updates_context_id: target ? target.id : null }),
    });
    const turn = await api(`/api/conversations/${conversation.id}/messages`, {
      method: "POST",
      body: JSON.stringify({ message }),
    });
    renderConversation(turn.conversation, true);
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
  loadUpdatableContexts();
  try {
    renderConversations(await api("/api/conversations"));
  } catch (error) {
    conversationList.textContent = error.message;
  }
}

// Product Owner and admin can also update an approved context through a conversation.
async function loadUpdatableContexts() {
  const allowed = currentRole === "admin" || currentRole === "product_owner";
  conversationTargetField.hidden = true;
  if (!allowed) return;
  try {
    updatableContexts = (await api("/api/contexts")).filter((item) => item.status === "approved")
      .sort((a, b) => a.name.localeCompare(b.name));
  } catch {
    updatableContexts = [];
  }
  const previous = conversationTarget.value;
  conversationTarget.replaceChildren(new Option(t("conversations.target_new"), ""));
  if (updatableContexts.length) {
    const group = document.createElement("optgroup");
    group.label = t("conversations.target_update_group");
    updatableContexts.forEach((item) => group.append(new Option(item.name, item.id)));
    conversationTarget.append(group);
  }
  conversationTarget.value = updatableContexts.some((item) => item.id === previous) ? previous : "";
  conversationTargetField.hidden = !updatableContexts.length;
  syncConversationPlaceholder();
}

function syncConversationPlaceholder() {
  const target = updatableContexts.find((item) => item.id === conversationTarget.value);
  conversationStartMessage.placeholder = target
    ? t("conversations.update_placeholder", { name: target.name })
    : t("conversations.prompt_placeholder");
}

conversationTarget.addEventListener("change", syncConversationPlaceholder);

function fillContextForm(context, status = "draft") {
  window.leadFinder?.syncReview({ ...context, status });
  reviewChanges.hidden = !pendingUpdate;
  saveDraftButton.hidden = currentRole === "sales" || Boolean(pendingUpdate);
  approveContextButton.textContent = pendingUpdate ? t("review.save_changes") : t("review.approve");
  window.contextHistory?.syncReview(pendingUpdate ? null : (context.id || currentContextId));
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

async function reviewConversationChanges() {
  saveToPortfolio.disabled = true;
  saveToPortfolio.textContent = t("builder.preparing");
  setStatus(chatStatus, t("builder.preparing_changes"), "success");
  try {
    const proposal = await api(`/api/conversations/${currentConversation.id}/update-proposal`, { method: "POST" });
    currentContextId = proposal.context_id;
    pendingUpdate = { conversationId: currentConversation.id };
    reviewOrigin = "builder";
    backFromReview.textContent = t("review.back");
    fillContextForm(proposal.proposal, "approved");
    renderContextChanges(proposal.changes, reviewChangesList);
    renderConversation(currentConversation);
    showView("review");
  } catch (error) {
    renderConversation(currentConversation);
    setStatus(chatStatus, error.message);
  }
}

async function saveConversationContext() {
  if (!currentConversation?.is_ready_to_save || currentConversation.portfolio_context_id) return;
  if (currentConversation.updates_context_id) return reviewConversationChanges();
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
      body: JSON.stringify({
        context: readContextForm(),
        status,
        publish_upload_ids: publishUploadIds,
        source: pendingUpdate ? "conversation" : "form",
        conversation_id: pendingUpdate ? pendingUpdate.conversationId : null,
      }),
    });
    pendingUpdate = null;
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

function appendKnowledgeMessage(text, role, sources = [], nearMisses = [], animate = false) {
  const row = appendMessage(knowledgeMessages, text, role, t("knowledge.assistant_name"), animate);
  if (role === "assistant" && sources.length) {
    const links = document.createElement("div");
    links.className = "message-sources";
    // Number the chips only when the answer itself cites [Source N].
    const numbered = /\[Source \d+\]/.test(text);
    sources.forEach((source, index) => {
      const label = numbered ? `[${index + 1}] ${source.title}` : source.title;
      // Public pages open directly; uploads and contexts open in the source viewer.
      const viewable = source.kind === "upload" || source.kind === "context";
      const chip = document.createElement(viewable ? "button" : source.url ? "a" : "span");
      if (viewable) {
        chip.type = "button";
        chip.addEventListener("click", () => openSourcePanel(source, chip));
      } else if (source.url) {
        chip.href = source.url;
        chip.target = "_blank";
        chip.rel = "noopener noreferrer";
      }
      chip.textContent = label;
      links.append(chip);
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

const sourcePanel = document.querySelector("#source-panel");
const sourcePanelKind = document.querySelector("#source-panel-kind");
const sourcePanelTitle = document.querySelector("#source-panel-title");
const sourcePanelPassages = document.querySelector("#source-panel-passages");
const sourcePanelOpen = document.querySelector("#source-panel-open");
let sourcePanelReturnFocus = null;
let sourcePanelAction = null;

function openSourcePanel(source, trigger) {
  sourcePanelReturnFocus = trigger;
  sourcePanelKind.textContent = t(`source_panel.kind_${source.kind}`);
  sourcePanelTitle.textContent = source.title;
  sourcePanelPassages.replaceChildren();
  (source.passages || []).forEach((passage) => {
    const quote = document.createElement("blockquote");
    quote.textContent = passage;
    sourcePanelPassages.append(quote);
  });
  if (!(source.passages || []).length) {
    const empty = document.createElement("p");
    empty.className = "source-panel-empty";
    empty.textContent = t("source_panel.no_passages");
    sourcePanelPassages.append(empty);
  }
  if (source.kind === "context") {
    sourcePanelOpen.textContent = t("source_panel.open_context");
    sourcePanelAction = () => { closeSourcePanel(); openContext(source.item_id); };
  } else {
    // Browsers can show a PDF; a Word file can only be downloaded.
    const isPdf = /\.pdf$/i.test(source.title);
    sourcePanelOpen.textContent = t(isPdf ? "source_panel.open_pdf" : "source_panel.download");
    sourcePanelAction = () => window.open(`/api/uploads/${source.item_id}${isPdf ? "?inline=true" : ""}`, "_blank", "noopener");
  }
  window.leadFinder?.syncSourcePanel(source);
  sourcePanel.hidden = false;
  document.querySelector("#source-panel-close").focus();
}

function closeSourcePanel() {
  if (sourcePanel.hidden) return;
  sourcePanel.hidden = true;
  sourcePanelReturnFocus?.focus();
}

sourcePanelOpen.addEventListener("click", () => sourcePanelAction?.());
document.querySelector("#source-panel-close").addEventListener("click", closeSourcePanel);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeSourcePanel();
});

const studioFrame = document.querySelector("#studio-frame");
const studioStatus = document.querySelector("#studio-status");
let studioLastLink = "";

async function openMarketingStudio(link = null) {
  showView("marketing");
  studioStatus.textContent = t("marketing.loading");
  studioStatus.hidden = false;
  try {
    // Signed links are single-use and short-lived, so fetch one per opening.
    studioLastLink = link || (await api("/api/studio/link")).url;
    studioFrame.src = studioLastLink;
  } catch (error) {
    studioStatus.textContent = error.message || t("marketing.unavailable");
  }
}

studioFrame.addEventListener("load", () => {
  if (studioFrame.src) studioStatus.hidden = true;
});

document.querySelector("#studio-new-tab").addEventListener("click", async () => {
  // A fresh link: the one used by the frame may already be spent. Safari and
  // other browsers that refuse cookies in embedded frames can work from here.
  const tab = window.open("about:blank", "_blank");
  try {
    const { url } = await api("/api/studio/link");
    tab.location.href = url;
  } catch (error) {
    tab.close();
    studioStatus.textContent = error.message || t("marketing.unavailable");
    studioStatus.hidden = false;
  }
});

function appendStudioOffer(marketingRequest, sources, conversationId) {
  const row = document.createElement("div");
  row.className = "message-row assistant studio-offer-row";
  const card = document.createElement("div");
  card.className = "studio-offer";
  card.setAttribute("role", "group");
  card.setAttribute("aria-label", t("studio.offer_title"));

  const badge = document.createElement("span");
  badge.className = "studio-offer-badge";
  badge.textContent = t(`studio.format_${marketingRequest.format}`);
  const title = document.createElement("h3");
  title.textContent = t("studio.offer_title");
  const brief = document.createElement("p");
  brief.className = "studio-offer-brief";
  brief.textContent = marketingRequest.brief;

  const actions = document.createElement("div");
  actions.className = "studio-offer-actions";
  const yes = document.createElement("button");
  yes.type = "button";
  yes.className = "primary-button";
  yes.textContent = t("studio.offer_yes");
  const no = document.createElement("button");
  no.type = "button";
  no.className = "text-button";
  no.textContent = t("studio.offer_no");
  const status = document.createElement("p");
  status.className = "studio-offer-status";
  status.setAttribute("role", "status");

  yes.addEventListener("click", async () => {
    yes.disabled = true;
    no.disabled = true;
    status.textContent = t("studio.preparing");
    try {
      const { url } = await api("/api/studio/projects", {
        method: "POST",
        body: JSON.stringify({ marketing_request: marketingRequest, conversation_id: conversationId, sources }),
      });
      await openMarketingStudio(url);
      status.textContent = "";
    } catch (error) {
      status.textContent = error.message;
      yes.disabled = false;
      no.disabled = false;
    }
  });
  no.addEventListener("click", () => {
    card.classList.add("dismissed");
    actions.remove();
    status.textContent = t("studio.dismissed");
  });

  actions.append(yes, no);
  card.append(badge, title, brief, actions, status);
  row.append(card);
  knowledgeMessages.append(row);
  knowledgeMessages.scrollTop = knowledgeMessages.scrollHeight;
}

function resetKnowledgeChat() {
  closeSourcePanel();
  knowledgeConversationId = null;
  knowledgeMessages.replaceChildren();
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
  conversation.messages.forEach((message) => appendKnowledgeMessage(message.content, message.role));
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

contextUpload.addEventListener("change", async () => {
  const file = contextUpload.files[0];
  if (!file || !currentConversation) return;
  setStatus(chatStatus, t("uploads.processing"), "success");
  try {
    const upload = await uploadDocument(file, "context_evidence", currentConversation.id);
    const discussion = await api(`/api/uploads/${upload.id}/discuss`, { method: "POST" });
    currentConversation = discussion.conversation;
    renderConversation(currentConversation, true);
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
    pendingUpdate = null;
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
    renderConversation(currentConversation, true);
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
  setStatus(knowledgeStatus, "");
  // Placeholder where the answer will appear, instead of a status line under the composer.
  const pendingRow = appendMessage(knowledgeMessages, "", "assistant", t("knowledge.assistant_name"));
  const pendingMessage = pendingRow.querySelector(".message");
  pendingMessage.classList.add("pending");
  pendingMessage.append(...Array.from({ length: 3 }, () => document.createElement("span")));
  pendingMessage.setAttribute("aria-label", t("knowledge.thinking"));
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
    pendingRow.remove();
    appendKnowledgeMessage(
      data.message,
      "assistant",
      data.sources,
      data.near_misses,
      true,
    );
    if (data.marketing_request) appendStudioOffer(data.marketing_request, data.sources, data.conversation_id);
    await loadKnowledgeHistory();
    setStatus(knowledgeStatus, "");
  } catch (error) {
    pendingRow.remove();
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
    if (item.dataset.view === "marketing" && !studioFrame.src) await openMarketingStudio();
    if (item.dataset.view === "knowledge") {
      await loadKnowledgeHistory();
      showKnowledgeHome();
    }
    if (item.dataset.view === "product-owner") {
      await Promise.all([loadPoHistory(), loadPoSettings()]);
      showPoHome();
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
  const { kind, id, action } = pendingDelete;
  try {
    if (action) {
      // Other modules (the Lead finder) bring their own delete.
      await action();
      deleteDialog.close();
      pendingDelete = null;
      return;
    }
    await api(kind === "conversation" ? `/api/conversations/${id}` : `/api/contexts/${id}`, {
      method: "DELETE",
    });
    deleteDialog.close();
    pendingDelete = null;
    if (kind === "conversation") {
      await loadConversations();
      if (!views.knowledge.hidden) await loadKnowledgeHistory();
      if (!views["product-owner"].hidden) {
        if (id === poConversationId) showPoHome();
        await loadPoHistory();
      }
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

// Product Owner: the Ask ibc group chat, plus a story proposal the user can edit
// and confirm. The server keeps every version. "Create in Azure DevOps" sends the
// version on screen with a confirmation id, so an edited, old or repeated click
// never creates a story the user did not see, and never creates it twice.
let poConversationId = null;
let poSettings = { devops_configured: false, can_create: false, targets: [], people: [], tags: [], project: "" };

function syncTagOptions() {
  let list = document.querySelector("#po-tag-options");
  if (!list) {
    list = document.createElement("datalist");
    list.id = "po-tag-options";
    document.body.append(list);
  }
  list.replaceChildren(...poSettings.tags.map((tag) => new Option(tag, tag)));
}

async function loadPoSettings() {
  try {
    poSettings = await api("/api/product-owner/settings");
    syncTagOptions();
  } catch (error) {
    poSettings = { devops_configured: false, can_create: false, targets: [], people: [], tags: [], project: "" };
  }
  return poSettings;
}

function poNotice() {
  if (!poSettings.devops_configured) return t("po.notice_not_connected");
  if (!poSettings.targets.length) return t("po.notice_unreachable");
  if (!poSettings.can_create) return t("po.notice_no_rights");
  return "";
}

function shortDate(value) {
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(date.valueOf())
    ? value
    : new Intl.DateTimeFormat(getLanguage(), { day: "numeric", month: "short", timeZone: "UTC" }).format(date);
}

function poTargetLabel(target) {
  if (target.kind === "backlog") return t("po.target_backlog");
  const name = target.timeframe === "current" ? t("po.target_current", { name: target.name }) : target.name;
  return target.start && target.finish ? `${name} (${shortDate(target.start)} – ${shortDate(target.finish)})` : name;
}

function newConfirmationId() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID();
  return `c-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

const WORK_ITEM_TYPES = ["User Story", "Bug", "Task", "Feature", "Epic"];

function typeKey(type) {
  return type.toLowerCase().replace(" ", "_");
}

function poField(labelText, control, hint = "") {
  const label = document.createElement("label");
  label.className = "field";
  const caption = document.createElement("span");
  caption.textContent = labelText;
  label.append(caption, control);
  if (hint) {
    const note = document.createElement("span");
    note.className = "hint";
    note.textContent = hint;
    label.append(note);
  }
  return label;
}

function poTextarea(name, value, rows) {
  const area = document.createElement("textarea");
  area.name = name;
  area.rows = rows;
  area.value = value;
  return area;
}

function storyDraftCard(record) {
  const editable = record.status === "draft" || record.status === "failed";
  const content = record.content;
  const row = document.createElement("div");
  row.className = "message-row assistant story-draft-row";
  row.dataset.draftId = record.id;

  const card = document.createElement("form");
  card.className = "story-draft";
  card.dataset.status = record.status;
  card.dataset.language = content.language || "";
  card.noValidate = true;
  card.setAttribute("aria-label", t("po.draft_title"));

  const header = document.createElement("div");
  header.className = "story-draft-header";
  const title = document.createElement("h3");
  title.textContent = t("po.draft_title");
  const badge = document.createElement("span");
  badge.className = "story-draft-badge";
  const ready = editable && !record.missing.length;
  badge.textContent = t(`po.status_${record.status === "draft" && ready ? "ready" : record.status}`);
  const version = document.createElement("span");
  version.className = "story-draft-version";
  version.textContent = t("po.version", { n: record.version });
  header.append(title, badge, version);
  card.append(header);

  if (record.status === "created" && record.devops_id) {
    const created = document.createElement("p");
    created.className = "story-draft-created";
    const link = document.createElement("a");
    link.href = record.devops_url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = `#${record.devops_id} — ${content.title}`;
    created.append(t("po.created_in_devops"), " ", link);
    card.append(created);
  }

  if (record.description) {
    const sentence = document.createElement("p");
    sentence.className = "story-draft-sentence";
    sentence.textContent = record.description;
    card.append(sentence);
  }

  const grid = document.createElement("div");
  grid.className = "form-grid story-draft-grid";
  const typeSelect = document.createElement("select");
  typeSelect.name = "work_item_type";
  WORK_ITEM_TYPES.forEach((type) => typeSelect.add(new Option(t(`po.type.${typeKey(type)}`), type)));
  typeSelect.value = content.work_item_type || "User Story";
  const typeField = poField(t("po.field.work_item_type"), typeSelect);
  const titleInput = document.createElement("input");
  titleInput.name = "title";
  titleInput.maxLength = 255;
  titleInput.value = content.title;
  const titleField = poField(t("po.field.title"), titleInput);
  titleField.classList.add("full-width");
  const points = document.createElement("select");
  points.name = "story_points";
  ["", 1, 2, 3, 5, 8, 13, 21].forEach((value) => {
    const option = new Option(value === "" ? "—" : String(value), String(value));
    if (String(content.story_points ?? "") === String(value)) option.selected = true;
    points.add(option);
  });
  const target = document.createElement("select");
  target.name = "target";
  target.add(new Option(t("po.target_choose"), ""));
  poSettings.targets.forEach((item) => {
    target.add(new Option(poTargetLabel(item), item.kind === "backlog" ? "backlog" : item.iteration_path));
  });
  const savedTarget = content.target_kind === "backlog" ? "backlog" : content.iteration_path || "";
  if (savedTarget && ![...target.options].some((option) => option.value === savedTarget)) {
    // Keep showing what was chosen even when the live list is unavailable.
    target.add(new Option(savedTarget === "backlog" ? t("po.target_backlog") : savedTarget, savedTarget));
  }
  target.value = savedTarget;
  const assignee = document.createElement("select");
  assignee.name = "assigned_to";
  assignee.add(new Option(t("po.nobody"), ""));
  poSettings.people.forEach((person) => assignee.add(new Option(person, person)));
  if (content.assigned_to && !poSettings.people.includes(content.assigned_to)) {
    assignee.add(new Option(content.assigned_to, content.assigned_to));
  }
  assignee.value = content.assigned_to || "";
  // Tags: existing ones only (new tags may not be created); suggestions from the live list.
  const tagsInput = document.createElement("input");
  tagsInput.name = "tags";
  tagsInput.value = (content.tags || []).join("; ");
  tagsInput.setAttribute("list", "po-tag-options");
  tagsInput.autocomplete = "off";

  const priority = document.createElement("select");
  priority.name = "priority";
  ["", 1, 2, 3, 4].forEach((value) => priority.add(new Option(value === "" ? "—" : String(value), String(value))));
  priority.value = String(content.priority ?? "");
  const remaining = document.createElement("input");
  remaining.name = "remaining_work";
  remaining.type = "number";
  remaining.min = "0";
  remaining.step = "0.5";
  remaining.value = content.remaining_work ?? "";
  const parent = document.createElement("input");
  parent.name = "parent_id";
  parent.type = "number";
  parent.min = "1";
  parent.value = content.parent_id ?? "";
  // Which fields a type has, as in TYPE_RULES in devops.py.
  const show = (field, types) => { field.dataset.types = types; return field; };
  const story = "User Story";
  grid.append(
    typeField,
    titleField,
    show(poField(t("po.field.role"), poTextarea("role", content.role, 2)), story),
    show(poField(t("po.field.capability"), poTextarea("capability", content.capability, 2)), story),
    show(Object.assign(poField(t("po.field.value"), poTextarea("value", content.value, 2)), { className: "field full-width" }), story),
    show(Object.assign(poField(t("po.field.description"), poTextarea("description", content.description || "", 4)), { className: "field full-width" }), "Bug|Task|Feature|Epic"),
    show(poField(t("po.field.entry_criteria"), poTextarea("entry_criteria", content.entry_criteria.join("\n"), 4), t("review.field.one_per_line")), story),
    show(poField(t("po.field.acceptance_criteria"), poTextarea("acceptance_criteria", content.acceptance_criteria.join("\n"), 4), t("review.field.one_per_line")), story),
    show(poField(t("po.field.story_points"), points), "User Story|Bug|Feature|Epic"),
    show(poField(t("po.field.remaining_work"), remaining), "Bug|Task"),
    poField(t("po.field.priority"), priority),
    poField(t("po.field.parent_id"), parent, t("po.parent_hint")),
    poField(t("po.field.target"), target),
    poField(t("po.field.assigned_to"), assignee),
    Object.assign(poField(t("po.field.tags"), tagsInput, t("po.tags_hint")), { className: "field full-width" }),
    Object.assign(poField(t("po.field.estimation_reason"), poTextarea("estimation_reason", content.estimation_reason, 2)), { className: "field full-width" }),
  );
  grid.querySelectorAll("input, textarea, select").forEach((control) => { control.disabled = !editable; });
  const applyType = () => grid.querySelectorAll("[data-types]").forEach((field) => {
    field.hidden = !field.dataset.types.split("|").includes(typeSelect.value);
  });
  typeSelect.addEventListener("change", applyType);
  applyType();
  badge.after(Object.assign(document.createElement("span"), {
    className: "story-draft-badge", textContent: t(`po.type.${typeKey(content.work_item_type || story)}`),
  }));
  card.append(grid);

  const notes = document.createElement("div");
  notes.className = "story-draft-notes";
  if (editable && record.missing.length) {
    const missing = document.createElement("p");
    missing.textContent = t("po.missing", { fields: record.missing.map((name) => t(`po.field.${name}`)).join(", ") });
    notes.append(missing);
  }
  if (record.status === "failed" || record.status === "uncertain") {
    const explain = document.createElement("p");
    explain.className = "story-draft-error";
    explain.textContent = t(`po.explain_${record.status}`);
    notes.append(explain);
    if (record.error) {
      const detail = document.createElement("p");
      detail.className = "story-draft-detail";
      detail.textContent = record.error;
      notes.append(detail);
    }
  }
  const notice = editable ? poNotice() : "";
  if (notice) {
    const info = document.createElement("p");
    info.textContent = notice;
    notes.append(info);
  }
  card.append(notes);

  const actions = document.createElement("div");
  actions.className = "story-draft-actions";
  const status = document.createElement("p");
  status.className = "story-draft-status";
  status.setAttribute("role", "status");

  if (editable) {
    const save = document.createElement("button");
    save.type = "button";
    save.className = "secondary-button";
    save.textContent = t("po.save");
    save.disabled = true;
    const create = document.createElement("button");
    create.type = "button";
    create.className = "primary-button";
    create.textContent = t("po.create");
    const canCreate = () => !card.classList.contains("is-dirty") && !record.missing.length && poSettings.can_create;
    create.disabled = !canCreate();

    const confirmBox = document.createElement("div");
    confirmBox.className = "story-draft-confirm";
    confirmBox.hidden = true;
    const confirmText = document.createElement("p");
    const yes = document.createElement("button");
    yes.type = "button";
    yes.className = "primary-button";
    yes.textContent = t("po.confirm_yes");
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "text-button";
    cancel.textContent = t("po.confirm_cancel");
    confirmBox.append(confirmText, yes, cancel);
    let confirmationId = null;

    card.addEventListener("input", () => {
      card.classList.add("is-dirty");
      save.disabled = false;
      create.disabled = true;
      confirmBox.hidden = true;
      status.textContent = t("po.unsaved");
    });
    save.addEventListener("click", async () => {
      save.disabled = true;
      status.textContent = t("po.saving");
      try {
        const updated = await api(`/api/product-owner/drafts/${record.id}`, {
          method: "PUT",
          body: JSON.stringify({ version: record.version, content: readStoryForm(card) }),
        });
        renderStoryDraft(updated, t("po.saved", { n: updated.version }));
      } catch (error) {
        save.disabled = false;
        status.textContent = error instanceof TypeError ? t("builder.unreachable") : error.message;
      }
    });
    create.addEventListener("click", () => {
      confirmationId = newConfirmationId();
      const chosen = target.options[target.selectedIndex]?.textContent || "";
      confirmText.textContent = t("po.confirm_text", { version: record.version, project: poSettings.project, target: chosen });
      confirmBox.hidden = false;
      create.disabled = true;
      yes.focus();
    });
    cancel.addEventListener("click", () => {
      confirmBox.hidden = true;
      confirmationId = null;
      create.disabled = !canCreate();
      create.focus();
    });
    yes.addEventListener("click", async () => {
      yes.disabled = true;
      cancel.disabled = true;
      status.textContent = t("po.creating");
      try {
        const result = await api(`/api/product-owner/drafts/${record.id}/create`, {
          method: "POST",
          body: JSON.stringify({ version: record.version, confirmation_id: confirmationId }),
        });
        renderStoryDraft(result, result.status === "created" ? t("po.created_status", { id: result.devops_id }) : "");
      } catch (error) {
        if (error instanceof TypeError) {
          // The answer was lost, not necessarily the request. Retrying with the
          // same confirmation id is safe: the server returns the stored outcome.
          status.textContent = t("po.connection_lost");
          yes.textContent = t("po.retry_safe");
          yes.disabled = false;
          return;
        }
        status.textContent = error.message;
        await reloadStoryDrafts();
      }
    });
    actions.append(save, create);
    card.append(actions, confirmBox, status);
  } else if (record.status === "uncertain" || record.status === "creating") {
    const check = document.createElement("button");
    check.type = "button";
    check.className = "secondary-button";
    check.textContent = t(record.status === "uncertain" ? "po.check" : "po.refresh");
    check.addEventListener("click", async () => {
      check.disabled = true;
      status.textContent = t("po.checking");
      try {
        if (record.status === "uncertain") {
          renderStoryDraft(await api(`/api/product-owner/drafts/${record.id}/check`, { method: "POST" }));
        } else {
          await reloadStoryDrafts();
        }
      } catch (error) {
        check.disabled = false;
        status.textContent = error instanceof TypeError ? t("builder.unreachable") : error.message;
      }
    });
    actions.append(check);
    card.append(actions, status);
  } else {
    card.append(status);
  }
  row.append(card);
  return row;
}

function readStoryForm(card) {
  const value = (name) => card.elements[name].value;
  const lines = (name) => value(name).split("\n").map((line) => line.trim()).filter(Boolean);
  const target = value("target");
  return {
    title: value("title").trim(),
    role: value("role").trim(),
    capability: value("capability").trim(),
    value: value("value").trim(),
    entry_criteria: lines("entry_criteria"),
    acceptance_criteria: lines("acceptance_criteria"),
    story_points: value("story_points") ? Number(value("story_points")) : null,
    estimation_reason: value("estimation_reason").trim(),
    target_kind: target === "backlog" ? "backlog" : target ? "sprint" : null,
    iteration_path: target && target !== "backlog" ? target : null,
    assigned_to: value("assigned_to") || null,
    work_item_type: value("work_item_type") || "User Story",
    description: value("description").trim(),
    remaining_work: value("remaining_work") === "" ? null : Number(value("remaining_work")),
    priority: value("priority") ? Number(value("priority")) : null,
    parent_id: value("parent_id") ? Number(value("parent_id")) : null,
    tags: value("tags").split(/[;,]/).map((tag) => tag.trim()).filter(Boolean),
    // Not a form field: kept from the proposal so an edit does not change the story's language.
    language: card.dataset.language || null,
  };
}

function placeCard(row, existing, moveToEnd) {
  // A new answer moves the card to the end; saving or confirming keeps it where it is.
  if (existing && !moveToEnd) existing.replaceWith(row);
  else {
    existing?.remove();
    poMessages.append(row);
  }
}

function scrollToRow(row) {
  const offset = row.getBoundingClientRect().top - poMessages.getBoundingClientRect().top;
  poMessages.scrollTop += offset - 12;
}

function renderStoryDraft(record, message = "", moveToEnd = false) {
  const existing = poMessages.querySelector(`.story-draft-row[data-draft-id="${record.id}"]`);
  const row = storyDraftCard(record);
  placeCard(row, existing, moveToEnd);
  if (message) row.querySelector(".story-draft-status").textContent = message;
}

function hasUnsavedStoryEdits() {
  return Boolean(poMessages.querySelector(".story-draft.is-dirty"));
}

async function reloadStoryDrafts() {
  if (!poConversationId) return;
  const drafts = await api(`/api/product-owner/conversations/${poConversationId}/drafts`);
  drafts.forEach((record) => renderStoryDraft(record));  // in place
}

// What SIP read from Azure DevOps: a list per status, or one story, with real links.
function workItemLink(item) {
  const link = document.createElement("a");
  link.href = item.url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = `#${item.id}`;
  return link;
}

function workItemResultCard(result) {
  const row = document.createElement("div");
  row.className = "message-row assistant work-items-row";
  row.dataset.resultId = result.id;
  const card = document.createElement("section");
  card.className = "work-items";
  card.setAttribute("aria-label", result.label);
  const title = document.createElement("h3");
  title.textContent = result.label;
  card.append(title);
  if (result.error) {
    const error = document.createElement("p");
    error.className = "work-items-error";
    error.textContent = result.error;
    card.append(error);
  } else if (result.detail) {
    const detail = result.detail;
    const head = document.createElement("p");
    head.className = "work-items-head";
    head.append(workItemLink(detail), ` ${detail.title}`);
    const meta = document.createElement("p");
    meta.className = "work-items-meta";
    meta.textContent = [
      WORK_ITEM_TYPES.includes(detail.work_item_type) ? t(`po.type.${typeKey(detail.work_item_type)}`) : detail.work_item_type,
      detail.state,
      detail.priority != null ? `${t("po.field.priority")} ${detail.priority}` : "",
      detail.remaining_work != null ? `${t("po.field.remaining_work")}: ${detail.remaining_work}` : "",
      detail.parent_id ? `${t("po.field.parent_id")} #${detail.parent_id}` : "",
      detail.story_points != null ? t("po.points", { n: detail.story_points }) : "",
      detail.assigned_to || t("po.unassigned"),
      detail.iteration_path,
      (detail.tags || []).length ? `${t("po.field.tags")}: ${detail.tags.join(", ")}` : "",
    ].filter(Boolean).join(" · ");
    card.append(head, meta);
    [["description", "po.change_field.description"], ["entry_criteria", "po.change_field.entry_criteria"],
      ["acceptance_criteria", "po.change_field.acceptance_criteria"]].forEach(([name, key]) => {
      const label = document.createElement("strong");
      label.textContent = t(key);
      const text = document.createElement("p");
      text.className = "work-items-text";
      text.textContent = detail[name] || "—";
      card.append(label, text);
    });
  } else if (!result.items.length) {
    const empty = document.createElement("p");
    empty.className = "work-items-meta";
    empty.textContent = t("po.no_items");
    card.append(empty);
  } else {
    const groups = new Map();
    result.items.forEach((item) => {
      if (!groups.has(item.state)) groups.set(item.state, []);
      groups.get(item.state).push(item);
    });
    groups.forEach((items, state) => {
      const heading = document.createElement("h4");
      heading.textContent = `${state} (${items.length})`;
      const list = document.createElement("ul");
      items.forEach((item) => {
        const entry = document.createElement("li");
        const meta = document.createElement("span");
        meta.className = "work-items-meta";
        meta.textContent = [
          WORK_ITEM_TYPES.includes(item.work_item_type) ? t(`po.type.${typeKey(item.work_item_type)}`) : item.work_item_type,
          item.story_points != null ? t("po.points", { n: item.story_points }) : "",
          item.assigned_to || t("po.unassigned"),
        ].filter(Boolean).join(" · ");
        entry.append(workItemLink(item), ` ${item.title} `, meta);
        list.append(entry);
      });
      card.append(heading, list);
    });
  }
  row.append(card);
  return row;
}

function renderWorkItemResult(result) {
  poMessages.append(workItemResultCard(result));
}

// A proposed change to an existing story: each field as current -> new, confirmed
// in two steps like a new story. Changes are made by asking in the chat.
function workItemChangeCard(record) {
  const row = document.createElement("div");
  row.className = "message-row assistant story-draft-row";
  row.dataset.changeId = record.id;
  const card = document.createElement("div");
  card.className = "story-draft work-item-change";
  card.dataset.status = record.status;
  card.setAttribute("role", "group");

  const header = document.createElement("div");
  header.className = "story-draft-header";
  const title = document.createElement("h3");
  const typeName = WORK_ITEM_TYPES.includes(record.work_item_type) ? t(`po.type.${typeKey(record.work_item_type)}`) : record.work_item_type;
  title.append(t("po.change_title_type", { type: typeName }), " ", workItemLink({ id: record.work_item_id, url: record.url }));
  const badge = document.createElement("span");
  badge.className = "story-draft-badge";
  badge.textContent = t(`po.change_status_${record.status}`);
  const version = document.createElement("span");
  version.className = "story-draft-version";
  version.textContent = t("po.version", { n: record.version });
  header.append(title, badge, version);
  const name = document.createElement("p");
  name.className = "story-draft-sentence";
  name.textContent = record.title;
  card.append(header, name);

  const table = document.createElement("table");
  table.className = "change-table";
  const head = document.createElement("tr");
  ["po.change_col_field", "po.change_col_current", "po.change_col_new"].forEach((key) => {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = t(key);
    head.append(cell);
  });
  table.append(head);
  record.changes.forEach((change) => {
    const line = document.createElement("tr");
    const field = document.createElement("th");
    field.scope = "row";
    field.textContent = t(`po.change_field.${change.field}`);
    const before = document.createElement("td");
    before.textContent = change.before || "—";
    const after = document.createElement("td");
    after.textContent = change.after || "—";
    line.append(field, before, after);
    table.append(line);
  });
  card.append(table);

  const notes = document.createElement("div");
  notes.className = "story-draft-notes";
  const warn = (text, error = false) => {
    const note = document.createElement("p");
    if (error) note.className = "story-draft-error";
    note.textContent = text;
    notes.append(note);
  };
  const newState = record.changes.find((change) => change.field === "state")?.after;
  if (newState === "Active") warn(t("po.warn_active"));
  if (newState === "Resolved") warn(t("po.warn_resolved"));
  if (record.status === "failed" || record.status === "uncertain") warn(t(`po.change_explain_${record.status}`), true);
  if (record.error) warn(record.error);
  card.append(notes);

  const actions = document.createElement("div");
  actions.className = "story-draft-actions";
  const status = document.createElement("p");
  status.className = "story-draft-status";
  status.setAttribute("role", "status");

  if (record.status === "draft" || record.status === "failed") {
    const apply = document.createElement("button");
    apply.type = "button";
    apply.className = "primary-button";
    apply.textContent = t("po.change_apply");
    apply.disabled = !poSettings.can_create;
    const confirmBox = document.createElement("div");
    confirmBox.className = "story-draft-confirm";
    confirmBox.hidden = true;
    const confirmText = document.createElement("p");
    confirmText.textContent = t("po.change_confirm_text", { id: record.work_item_id, version: record.version });
    const yes = document.createElement("button");
    yes.type = "button";
    yes.className = "primary-button";
    yes.textContent = t("po.change_confirm_yes");
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "text-button";
    cancel.textContent = t("po.confirm_cancel");
    confirmBox.append(confirmText, yes, cancel);
    let confirmationId = null;
    apply.addEventListener("click", () => {
      confirmationId = newConfirmationId();
      confirmBox.hidden = false;
      apply.disabled = true;
      yes.focus();
    });
    cancel.addEventListener("click", () => {
      confirmBox.hidden = true;
      confirmationId = null;
      apply.disabled = false;
      apply.focus();
    });
    yes.addEventListener("click", async () => {
      yes.disabled = true;
      cancel.disabled = true;
      status.textContent = t("po.change_applying");
      try {
        const result = await api(`/api/product-owner/changes/${record.id}/apply`, {
          method: "POST",
          body: JSON.stringify({ version: record.version, confirmation_id: confirmationId }),
        });
        renderWorkItemChange(result, result.status === "applied" ? t("po.change_applied_status", { id: result.work_item_id }) : "");
      } catch (error) {
        if (error instanceof TypeError) {
          status.textContent = t("po.connection_lost");
          yes.textContent = t("po.retry_safe");
          yes.disabled = false;
          return;
        }
        status.textContent = error.message;
        cancel.disabled = false;
      }
    });
    if (!poSettings.can_create) warn(t("po.notice_no_rights"));
    actions.append(apply);
    card.append(actions, confirmBox, status);
  } else if (record.status === "uncertain" || record.status === "applying") {
    const check = document.createElement("button");
    check.type = "button";
    check.className = "secondary-button";
    check.textContent = t("po.check");
    check.addEventListener("click", async () => {
      check.disabled = true;
      status.textContent = t("po.checking");
      try {
        renderWorkItemChange(await api(`/api/product-owner/changes/${record.id}/check`, { method: "POST" }));
      } catch (error) {
        check.disabled = false;
        status.textContent = error instanceof TypeError ? t("builder.unreachable") : error.message;
      }
    });
    actions.append(check);
    card.append(actions, status);
  } else {
    card.append(status);
  }
  row.append(card);
  return row;
}

function renderWorkItemChange(record, message = "", moveToEnd = false) {
  const existing = poMessages.querySelector(`.story-draft-row[data-change-id="${record.id}"]`);
  const row = workItemChangeCard(record);
  placeCard(row, existing, moveToEnd);
  if (message) row.querySelector(".story-draft-status").textContent = message;
}

function appendSplitSuggestion(titles) {
  const row = document.createElement("div");
  row.className = "message-row assistant story-split-row";
  const block = document.createElement("div");
  block.className = "story-split";
  const label = document.createElement("strong");
  label.textContent = t("po.split_title");
  const list = document.createElement("ol");
  titles.forEach((title) => {
    const item = document.createElement("li");
    item.textContent = title;
    list.append(item);
  });
  block.append(label, list);
  row.append(block);
  poMessages.append(row);
}

function showPoHome() {
  poConversationId = null;
  poHome.hidden = false;
  poChat.hidden = true;
  document.body.classList.remove("chat-open");
  poStartMessage.value = "";
  poStartMessage.focus();
}

function showPoConversation() {
  poHome.hidden = true;
  poChat.hidden = false;
  document.body.classList.add("chat-open");
}

function resetPoChat() {
  poConversationId = null;
  poMessages.replaceChildren();
  setStatus(poStatus, "");
  poInput.value = "";
  resizeTextArea(poInput);
}

async function openPoConversation(conversationId) {
  const [conversation, timeline] = await Promise.all([
    api(`/api/conversations/${conversationId}`),
    api(`/api/product-owner/conversations/${conversationId}/timeline`),
    loadPoSettings(),
  ]);
  resetPoChat();
  poConversationId = conversation.id;
  // Same-second entries keep messages first, so a card follows the answer it belongs to.
  const entries = [
    ...conversation.messages.map((message, index) => ({ at: message.created_at, order: 0, index, show: () =>
      appendMessage(poMessages, message.content, message.role, t("po.assistant_name")) })),
    ...timeline.results.map((result) => ({ at: result.created_at, order: 1, show: () => renderWorkItemResult(result) })),
    ...timeline.drafts.map((record) => ({ at: record.updated_at, order: 1, show: () => renderStoryDraft(record, "", true) })),
    ...timeline.changes.map((record) => ({ at: record.updated_at, order: 1, show: () => renderWorkItemChange(record, "", true) })),
  ];
  entries.sort((a, b) => (a.at < b.at ? -1 : a.at > b.at ? 1 : a.order - b.order || (a.index ?? 0) - (b.index ?? 0)));
  entries.forEach((entry) => entry.show());
  poHistory.value = conversation.id;
  showPoConversation();
  // Built while hidden, so scroll once visible: continue at the latest message.
  poMessages.scrollTo({ top: poMessages.scrollHeight, behavior: "instant" });
  poInput.focus();
}

async function loadPoHistory() {
  const conversations = await api("/api/conversations?kind=product_owner");
  poHistory.replaceChildren(new Option(t("knowledge.history"), ""));
  poConversationList.replaceChildren();
  conversations.forEach((conversation) => {
    poHistory.add(new Option(conversation.title, conversation.id));
    const row = document.createElement("div");
    row.className = "conversation-row";
    const open = document.createElement("button");
    open.type = "button";
    open.className = "row-open";
    open.addEventListener("click", () => openPoConversation(conversation.id));
    const description = document.createElement("span");
    const title = document.createElement("span");
    title.className = "conversation-title";
    title.textContent = conversation.title;
    const preview = document.createElement("span");
    preview.className = "conversation-preview";
    preview.textContent = conversation.preview || t("conversations.no_messages");
    description.append(title, preview);
    const updated = document.createElement("span");
    updated.className = "conversation-date";
    updated.textContent = formatDate(conversation.updated_at);
    open.append(description, document.createElement("span"), updated);
    row.append(open, deleteButton(t("conversations.delete_aria", { title: conversation.title }), () =>
      requestDelete("conversation", conversation.id, conversation.title)));
    poConversationList.append(row);
  });
  if (!conversations.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = t("conversations.empty_title");
    poConversationList.append(empty);
  }
  poHistory.value = poConversationId || "";
}

poHistory.addEventListener("change", async () => {
  if (!poHistory.value) return showPoHome();
  await openPoConversation(poHistory.value);
});

poStartForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = poStartMessage.value.trim();
  if (!message) return;
  poStartSend.disabled = true;
  resetPoChat();
  await loadPoSettings();
  poInput.value = message;
  showPoConversation();
  poChatForm.requestSubmit();
  poStartSend.disabled = false;
});

poStartMessage.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    poStartForm.requestSubmit();
  }
});

poChatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = poInput.value.trim();
  if (!message) return;
  if (hasUnsavedStoryEdits()) {
    // The assistant works from the saved version; unsaved edits would be lost.
    setStatus(poStatus, t("po.save_first"));
    return;
  }
  const userRow = appendMessage(poMessages, message, "user");
  poMessages.scrollTop = poMessages.scrollHeight;
  poInput.value = "";
  resizeTextArea(poInput);
  poSend.disabled = true;
  setStatus(poStatus, "");
  const pendingRow = appendMessage(poMessages, "", "assistant", t("po.assistant_name"));
  poMessages.scrollTop = poMessages.scrollHeight;
  const pendingMessage = pendingRow.querySelector(".message");
  pendingMessage.classList.add("pending");
  pendingMessage.append(...Array.from({ length: 3 }, () => document.createElement("span")));
  pendingMessage.setAttribute("aria-label", t("po.thinking"));
  try {
    const data = await api("/api/product-owner/chat", {
      method: "POST",
      body: JSON.stringify({ message, conversation_id: poConversationId, language: getLanguage() }),
    });
    poConversationId = data.conversation_id;
    pendingRow.remove();
    appendMessage(poMessages, data.message, "assistant", t("po.assistant_name"), true);
    if (data.split_suggestion.length) appendSplitSuggestion(data.split_suggestion);
    if (data.draft) renderStoryDraft(data.draft, "", true);
    if (data.result) renderWorkItemResult(data.result);
    if (data.change) renderWorkItemChange(data.change, "", true);
    // Show the answer from its first line, with the card below it.
    scrollToRow(userRow);
    await loadPoHistory();
  } catch (error) {
    pendingRow.remove();
    userRow.remove();
    poInput.value = message;
    resizeTextArea(poInput);
    setStatus(poStatus, error instanceof TypeError ? t("builder.unreachable") : error.message);
  } finally {
    poSend.disabled = false;
    poInput.focus();
  }
});

poInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    poChatForm.requestSubmit();
  }
});
poInput.addEventListener("input", () => resizeTextArea(poInput));
newPoChat.addEventListener("click", () => {
  showPoHome();
  loadPoHistory();
});

// Home: "Your digital team". Each action opens an existing SIP view through its
// navigation item, so the home page adds no second route into any feature.
// data-roles on each action mirrors _role_allows in main.py.
const specialistCards = [...document.querySelectorAll(".specialist[data-specialist]")];
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

function applySpecialistAvailability() {
  specialistCards.forEach((card) => {
    const actions = [...card.querySelectorAll(".specialist-action")];
    actions.forEach((action) => {
      action.hidden = !action.dataset.roles.split(" ").includes(currentRole) || action.dataset.available === "false";
    });
    const usable = actions.filter((action) => !action.hidden);
    const notice = card.querySelector(".specialist-unavailable");
    if (notice && actions.length) notice.hidden = usable.length > 0;
    card.classList.toggle("is-unavailable", usable.length === 0);
    // With exactly one action the whole card is its hit area; with two, each button is its own.
    card.classList.toggle("is-single-action", usable.length === 1);
  });
}

document.querySelectorAll(".specialist-action[data-view]").forEach((action) => {
  action.addEventListener("click", () => {
    const navItem = document.querySelector(`.nav-item[data-view="${action.dataset.view}"]`);
    if (navItem) navItem.click();
  });
});

document.querySelector("[data-developer-open]").addEventListener("click", async () => {
  // Open synchronously from the click so popup blockers allow the new tab.
  const tab = window.open("about:blank", "_blank");
  if (!tab) { alert(t("home.developer.popup_blocked")); return; }
  tab.opener = null;
  try {
    const { url } = await api("/api/developer/link");
    tab.location.replace(url);
  } catch (error) {
    tab.close();
    alert(error.message || t("home.developer.unavailable"));
  }
});

// Optional animation per specialist: drop <name>.mp4 next to the PNG in
// backend/app/avatars. Without a file, or when it fails, blocked autoplay or
// "reduce motion" apply, the still image stays and everything keeps working.
const homeVideoState = new Map(); // video element -> "failed" | "ready"
const homeVideoObserver = "IntersectionObserver" in window
  ? new IntersectionObserver((entries) => entries.forEach((entry) => {
    entry.target.dataset.inView = entry.isIntersecting ? "true" : "false";
    updateHomeVideo(entry.target);
  }), { threshold: 0.35 })
  : null;

function updateHomeVideo(video) {
  const shouldPlay = !views.home.hidden
    && !document.hidden
    && !reducedMotion.matches
    && video.dataset.inView === "true"
    && homeVideoState.get(video) !== "failed";
  if (!shouldPlay) {
    if (!video.paused) video.pause();
    return;
  }
  if (!video.getAttribute("src")) video.src = video.dataset.video;
  const attempt = video.play();
  if (attempt) attempt.catch(() => video.pause()); // autoplay blocked: keep the still image
}

const homeVideos = [...document.querySelectorAll(".specialist-video[data-video]")];

function syncHomeMedia() {
  homeVideos.forEach(updateHomeVideo);
  if (typeof requestRobotFrame === "function" && robotsActive()) {
    startRobots();
    requestRobotFrame();
  }
}

homeVideos.forEach((video) => {
  video.addEventListener("playing", () => video.closest(".specialist-stage").classList.add("has-video"));
  video.addEventListener("pause", () => video.closest(".specialist-stage").classList.remove("has-video"));
  video.addEventListener("error", () => {
    homeVideoState.set(video, "failed");
    video.closest(".specialist-stage").classList.remove("has-video");
    video.removeAttribute("src");
  });
  if (homeVideoObserver) homeVideoObserver.observe(video);
});
document.addEventListener("visibilitychange", syncHomeMedia);
reducedMotion.addEventListener?.("change", () => {
  document.querySelectorAll(".specialist-stage.is-alive").forEach((stage) => stage.classList.toggle("is-still", reducedMotion.matches));
  syncHomeMedia();
});

// Living robots: the eyes follow the pointer, blink, wander when nothing happens and
// now and then glance at a neighbour. Each robot is its still image with the eyes
// removed, plus the two eyes cut from the original as separate layers. Until both
// images have loaded, and always with "reduce motion", the original PNG stays.
const ROBOT_SIZE = 1254; // pixel grid of the source images the eye coordinates use
const GAZE_REACH = 15; // furthest an eye moves, in source pixels
const robots = [];
let pointer = null;
let lastPointerMove = 0;
let robotFrame = 0;

function loadImage(src) {
  const image = new Image();
  image.decoding = "async";
  image.src = src;
  return image.decode().then(() => image);
}

async function bringRobotToLife(live) {
  const stage = live.closest(".specialist-stage");
  const card = live.closest(".specialist");
  const eyes = live.dataset.eyes.split(";").map((eye) => eye.split(",").map(Number));
  try {
    await Promise.all([loadImage(live.dataset.base), loadImage(live.dataset.eyesSrc)]);
  } catch (error) {
    return; // keep the original still image
  }
  const body = document.createElement("div");
  body.className = "robot-body";
  const base = document.createElement("img");
  base.className = "robot-base";
  base.src = live.dataset.base;
  base.alt = "";
  body.append(base);
  const eyeElements = eyes.map(([cx, cy, r]) => {
    const eye = document.createElement("div");
    eye.className = "robot-eye";
    eye.style.cssText = `--cx: ${cx}; --cy: ${cy}; --r: ${r};`;
    eye.innerHTML = `<div class="robot-eye-gaze"><div class="robot-eye-lid"><img alt="" src="${live.dataset.eyesSrc}"></div></div>`;
    body.append(eye);
    return eye;
  });
  live.append(body);
  stage.classList.add("is-alive");

  const robot = {
    card,
    stage,
    eyeElements,
    centre: [
      eyes.reduce((sum, eye) => sum + eye[0], 0) / eyes.length / ROBOT_SIZE,
      eyes.reduce((sum, eye) => sum + eye[1], 0) / eyes.length / ROBOT_SIZE,
    ],
    radius: eyes.map((eye) => eye[2]),
    gaze: [0, 0],
    target: [0, 0],
    wanderUntil: 0,
  };
  robots.push(robot);
  scheduleBlink(robot);
  card.addEventListener("pointerenter", () => card.classList.add("is-perked"));
  card.addEventListener("pointerleave", () => card.classList.remove("is-perked"));
  card.addEventListener("focusin", () => card.classList.add("is-perked"));
  card.addEventListener("focusout", () => card.classList.remove("is-perked"));
  // Tapping the robot itself gets a happy squint; it does not navigate.
  stage.addEventListener("click", () => {
    stage.classList.remove("is-happy");
    void stage.offsetWidth;
    stage.classList.add("is-happy");
    window.setTimeout(() => stage.classList.remove("is-happy"), 700);
  });
  requestRobotFrame();
}

function robotsActive() {
  return !views.home.hidden && !document.hidden && !reducedMotion.matches;
}

function scheduleBlink(robot) {
  const wait = 2200 + Math.random() * 4200;
  window.setTimeout(() => {
    if (robotsActive()) {
      robot.stage.classList.remove("is-blinking");
      void robot.stage.offsetWidth;
      robot.stage.classList.add("is-blinking");
      // Sometimes a quick double blink.
      if (Math.random() < 0.2) window.setTimeout(() => {
        robot.stage.classList.remove("is-blinking");
        void robot.stage.offsetWidth;
        robot.stage.classList.add("is-blinking");
      }, 260);
    }
    scheduleBlink(robot);
  }, wait);
}

function chooseTargets(now) {
  const idle = !pointer || now - lastPointerMove > 3500;
  robots.forEach((robot, index) => {
    if (!idle) {
      const rect = robot.stage.getBoundingClientRect();
      const x = rect.left + robot.centre[0] * rect.width;
      const y = rect.top + robot.centre[1] * rect.height;
      const dx = pointer[0] - x;
      const dy = pointer[1] - y;
      const distance = Math.hypot(dx, dy) || 1;
      const strength = Math.min(1, distance / 260);
      robot.target = [(dx / distance) * strength, (dy / distance) * strength * 0.75];
      return;
    }
    if (now < robot.wanderUntil) return;
    const roll = Math.random();
    if (roll < 0.3 && robots.length > 1) {
      // Glance at a neighbour.
      const neighbour = robots[(index + (Math.random() < 0.5 ? 1 : robots.length - 1)) % robots.length];
      const direction = Math.sign(robots.indexOf(neighbour) - index) || 1;
      robot.target = [0.85 * direction, 0.1];
    } else if (roll < 0.55) {
      robot.target = [0, 0]; // straight at the viewer
    } else {
      robot.target = [(Math.random() * 2 - 1) * 0.7, (Math.random() * 2 - 1) * 0.45];
    }
    robot.wanderUntil = now + 1400 + Math.random() * 2600;
  });
}

function requestRobotFrame() {
  if (!robotFrame) robotFrame = window.requestAnimationFrame(animateRobots);
}

function animateRobots(now) {
  robotFrame = 0;
  if (!robotsActive() || !robots.length) return;
  chooseTargets(now);
  robots.forEach((robot) => {
    robot.gaze = robot.gaze.map((value, axis) => value + (robot.target[axis] - value) * 0.16);
    robot.eyeElements.forEach((eye, index) => {
      const scale = GAZE_REACH / (2 * robot.radius[index]) * 100;
      eye.style.setProperty("--gx", `${(robot.gaze[0] * scale).toFixed(2)}%`);
      eye.style.setProperty("--gy", `${(robot.gaze[1] * scale).toFixed(2)}%`);
    });
  });
  requestRobotFrame();
}

document.addEventListener("pointermove", (event) => {
  pointer = [event.clientX, event.clientY];
  lastPointerMove = performance.now();
  requestRobotFrame();
}, { passive: true });

function startRobots() {
  if (reducedMotion.matches) return;
  document.querySelectorAll(".robot-live").forEach((live) => {
    if (!live.closest(".specialist-stage").classList.contains("is-alive")) bringRobotToLife(live);
  });
}

applyTranslations();
applySpecialistAvailability();
resetKnowledgeChat();
loadCurrentUser();
loadConversations();
window.addEventListener("load", startRobots);
