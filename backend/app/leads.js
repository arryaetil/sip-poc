// Lead finder: an intake chat that agrees a search brief, then a lead list that fills
// while SIP searches. Uses the helpers of app.js (api, t, appendMessage, showView, ...).
// Wrapped in a function so its names never collide with app.js.
(() => {
  const ALLOWED_ROLES = ["admin", "sales"];
  const POLL_MS = 2500;
  const LEVELS = ["high", "medium", "low"];
  const POINTS = { high: 2, medium: 1, low: 0 };
  const SAM_SIGNALS = { rating: "Rating", reviews: "Reviews", vacancies: "Vacatures", chat: "Chattool" };
  const SAM_COPY = "Schaal (30): vestigingen × 2, max 20; reviews / 250, max 10. Pijn (30): rating onder 3,8: 12; onder 4,3: 6; onder 4,6: 3. Klachten (18) uitgesloten: geen reviewteksten in afwachting van privacybeoordeling. Koopsignaal (25): receptie 12, klantenservice 10, serviceadviseur 7; tel categorieën op + 3 bij minstens één vacature, max 25. Fit (15): geen chat gedetecteerd 6, service weekend gesloten 4, minstens 4 merken 5. A vanaf 65, B vanaf 45, C daaronder. Maximaal 82/100. Onbekend levert 0 punten op. Geen chat gedetecteerd bewijst geen afwezigheid. Google-cijfers dekken alleen gevonden vestigingen met hetzelfde websitedomein.";
  const sam = () => list?.brief.scoring === "sam_points";
  const rowPill = (row) => {
    const pill = scorePill(row.score.level);
    if (row.score.tier) pill.lastChild.textContent = `${row.score.tier} · ${row.score.points}/100`;
    return pill;
  };

  const $ = (selector) => document.querySelector(selector);
  const home = $("#lead-home");
  const intake = $("#lead-intake");
  const result = $("#lead-result");
  const contextSelect = $("#lead-context");
  const startForm = $("#lead-start-form");
  const startMessage = $("#lead-start-message");
  const startSend = $("#lead-start-send");
  const unavailable = $("#lead-unavailable");
  const listsElement = $("#lead-lists");
  const chatsSection = $("#lead-chats-section");
  const chatsElement = $("#lead-conversations");
  const messagesElement = $("#lead-messages");
  const chatForm = $("#lead-chat-form");
  const chatInput = $("#lead-message");
  const chatSend = $("#lead-send");
  const chatStatus = $("#lead-status");
  const intakeContext = $("#lead-intake-context");
  const briefTitle = $("#lead-brief-title");
  const briefBody = $("#lead-brief-body");
  const briefHint = $("#lead-brief-hint");
  const startSearch = $("#lead-start-search");
  const resultTitle = $("#lead-result-title");
  const resultMeta = $("#lead-result-meta");
  const resultNotice = $("#lead-result-notice");
  const progress = $("#lead-progress");
  const progressBar = $("#lead-progress-bar");
  const progressText = $("#lead-progress-text");
  const filters = $("#lead-filters");
  const search = $("#lead-search");
  const tableHead = $("#lead-table-head");
  const tableBody = $("#lead-table-body");
  const emptyState = $("#lead-empty");
  const exportLink = $("#lead-export");
  const drawer = $("#lead-drawer");
  const drawerKicker = $("#lead-drawer-kicker");
  const drawerTitle = $("#lead-drawer-title");
  const drawerBody = $("#lead-drawer-body");
  const drawerFooter = $("#lead-drawer-footer");

  let settings = { available: false, missing: null, max_leads: 50, retention_days: 90 };
  let contexts = []; // approved Business Contexts
  let websiteSources = []; // services and solutions from the ETIL / ibc group websites
  let session = { conversationId: null, contextId: null, contextName: "", brief: null, ready: false };
  let list = null;
  let shownRows = new Set();
  let filter = "all";
  let pollTimer = 0;
  let renderedSignature = "";
  let drawerReturnFocus = null;

  const allowed = () => ALLOWED_ROLES.includes(currentRole);
  const creator = (item) => (item.mine ? t("lead.by_you") : item.created_by ? t("lead.by", { name: item.created_by }) : "");

  function el(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined && text !== null) element.textContent = text;
    return element;
  }

  function domain(url) {
    try {
      return new URL(url).hostname.replace(/^www\./, "");
    } catch {
      return url;
    }
  }

  function sourceLabel(url) {
    try {
      const parsed = new URL(url);
      const path = parsed.pathname.replace(/\/$/, "");
      return `${parsed.hostname.replace(/^www\./, "")}${path.length > 1 ? path : ""}`;
    } catch {
      return url;
    }
  }

  function externalLink(href, text, className = "") {
    const link = el("a", className, text);
    link.href = href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.addEventListener("click", (event) => event.stopPropagation());
    return link;
  }

  function daysLeft(expiresAt) {
    const end = new Date(`${expiresAt.replace(" ", "T")}Z`);
    return Math.max(0, Math.ceil((end - Date.now()) / 86_400_000));
  }

  function columnLabel(column) {
    if (column === "country") return t("lead.col.country");
    if (column === "city") return t("lead.col.city");
    return column;
  }

  function scorePill(level) {
    const pill = el("span", `lead-score lead-score-${level || "none"}`);
    pill.append(el("span", "lead-score-dot"), el("span", "", level ? t(`lead.score.${level}`) : "–"));
    return pill;
  }

  function pendingDots(row) {
    const message = row.querySelector(".message");
    message.classList.add("pending");
    message.append(...Array.from({ length: 3 }, () => document.createElement("span")));
    message.setAttribute("aria-label", t("lead.thinking"));
  }

  // ------------------------------------------------------------------- views

  function show(part) {
    home.hidden = part !== "home";
    intake.hidden = part !== "intake";
    result.hidden = part !== "result";
    document.body.classList.toggle("chat-open", part === "intake");
    document.body.classList.toggle("lead-intake-open", part === "intake");
    if (part !== "result") stopPolling();
    closeDrawer(false);
    // Measured once visible; a hidden textarea has no height.
    if (part === "intake") requestAnimationFrame(() => resizeTextArea(chatInput));
  }

  async function openLeadFinder(contextId = null) {
    showView("lead");
    show("home");
    await loadHome(contextId);
    startMessage.focus();
  }

  async function loadHome(preselect = null) {
    const [loadedSettings, loadedContexts, loadedSources, lists, chats] = await Promise.all([
      api("/api/leads/settings").catch(() => settings),
      api("/api/contexts").catch(() => []),
      api("/api/leads/sources").catch(() => []),
      api("/api/leads/lists").catch(() => []),
      api("/api/leads/conversations").catch(() => []),
    ]);
    settings = loadedSettings;
    contexts = loadedContexts.filter((context) => context.status === "approved").sort((a, b) => a.name.localeCompare(b.name));
    websiteSources = loadedSources;
    $("#lead-lists-subtitle").textContent = t("lead.lists_subtitle", { days: settings.retention_days });
    renderContextOptions(preselect);
    renderAvailability();
    renderLists(lists);
    renderChats(chats);
  }

  // Everything a search can start from: Business Contexts first, then the website
  // services and solutions per organisation.
  function startingPoints() {
    return [...contexts, ...websiteSources];
  }

  function renderContextOptions(preselect) {
    const previous = preselect || contextSelect.value;
    contextSelect.replaceChildren(new Option(t("lead.context_placeholder"), ""));
    const group = (label, items) => {
      if (!items.length) return;
      const optgroup = document.createElement("optgroup");
      optgroup.label = label;
      items.forEach((item) => optgroup.append(new Option(item.name, item.id)));
      contextSelect.append(optgroup);
    };
    group(t("lead.group_contexts"), contexts);
    [...new Set(websiteSources.map((source) => source.organisation))].forEach((organisation) =>
      group(t("lead.group_website", { organisation }), websiteSources.filter((source) => source.organisation === organisation)));
    if (startingPoints().some((item) => item.id === previous)) contextSelect.value = previous;
  }

  function renderAvailability() {
    let notice = "";
    if (!settings.available) notice = t(`lead.unavailable_${settings.missing || "assistant"}`);
    else if (!startingPoints().length) notice = t("lead.no_contexts");
    unavailable.textContent = notice;
    unavailable.hidden = !notice;
    const usable = !notice;
    [contextSelect, startMessage, startSend, $("#lead-scoring")].forEach((control) => { control.disabled = !usable; });
    startForm.classList.toggle("is-disabled", !usable);
  }

  function countsBar(found, counts) {
    const bar = el("span", "lead-mini-bar");
    bar.setAttribute("aria-hidden", "true");
    LEVELS.forEach((level) => {
      const share = found ? (counts[level] || 0) / found : 0;
      if (!share) return;
      const part = el("span", `lead-mini-${level}`);
      part.style.flexGrow = String(share);
      bar.append(part);
    });
    return bar;
  }

  function listState(item) {
    if (item.status === "running") return { label: t("lead.state.running", { found: item.found, requested: item.requested }), className: "running" };
    if (item.status === "failed") return { label: t("lead.state.failed"), className: "failed" };
    if (item.status === "interrupted") return { label: t("lead.state.interrupted"), className: "failed" };
    return { label: t(item.found === 1 ? "lead.state.done_one" : "lead.state.done", { found: item.found }), className: "done" };
  }

  function renderLists(lists) {
    listsElement.replaceChildren();
    if (!lists.length) {
      const empty = el("div", "empty-state lead-lists-empty");
      empty.append(el("h2", "", t("lead.lists_empty_title")), el("p", "", t("lead.lists_empty_copy")));
      listsElement.append(empty);
      return;
    }
    lists.forEach((item) => {
      const row = el("div", "conversation-row lead-list-row");
      const open = el("button", "row-open lead-list-open");
      open.type = "button";
      open.addEventListener("click", () => openList(item.id));
      const description = el("span");
      description.append(
        el("span", "conversation-title", item.title),
        el("span", "conversation-preview", [item.context_name, creator(item)].filter(Boolean).join(" · ")),
      );
      const state = listState(item);
      const status = el("span", `status-chip lead-chip-${state.className}`, state.label);
      const dates = el("span", "conversation-date");
      dates.append(
        el("span", "", formatDate(item.created_at)),
        el("span", "lead-expiry", t("lead.expires_in", { days: daysLeft(item.expires_at) })),
      );
      open.append(description, status, dates);
      row.append(open);
      if (item.mine || currentRole === "admin") {
        row.append(deleteButton(t("lead.delete_list_aria", { title: item.title }), () => confirmDelete(
          item.title,
          t("lead.delete_list_description"),
          async () => { await api(`/api/leads/lists/${item.id}`, { method: "DELETE" }); await loadHome(); },
        )));
      } else {
        row.classList.add("read-only");
      }
      listsElement.append(row);
    });
  }

  function renderChats(chats) {
    chatsElement.replaceChildren();
    chatsSection.hidden = !chats.length;
    chats.forEach((chat) => {
      const row = el("div", "conversation-row");
      const open = el("button", "row-open");
      open.type = "button";
      open.addEventListener("click", () => openIntake(chat.id));
      const description = el("span");
      description.append(el("span", "conversation-title", chat.title), el("span", "conversation-preview", chat.preview || ""));
      open.append(description, el("span"), el("span", "conversation-date", formatDate(chat.updated_at)));
      row.append(open, deleteButton(t("conversations.delete_aria", { title: chat.title }), () => confirmDelete(
        chat.title,
        t("delete.conversation_description"),
        async () => { await api(`/api/leads/conversations/${chat.id}`, { method: "DELETE" }); await loadHome(); },
      )));
      chatsElement.append(row);
    });
  }

  function confirmDelete(name, description, action) {
    pendingDelete = { kind: "lead", id: null, action };
    deleteTitle.textContent = t("delete.heading", { name });
    deleteDescription.textContent = description;
    document.querySelector("#confirm-delete").textContent = t("delete.item_title");
    deleteDialog.showModal();
  }

  // ------------------------------------------------------------------- intake

  function resetIntake(contextId, contextName) {
    session = { conversationId: null, contextId, contextName, brief: null, ready: false };
    messagesElement.replaceChildren();
    setStatus(chatStatus, "");
    chatInput.value = "";
    resizeTextArea(chatInput);
    intakeContext.textContent = t("lead.for_context", { name: contextName });
    renderBrief(null, false);
  }

  async function openIntake(conversationId) {
    const data = await api(`/api/leads/conversations/${conversationId}`);
    resetIntake(data.context_id, data.context_name || "");
    session.conversationId = data.conversation.id;
    data.messages.forEach((message) => appendMessage(messagesElement, message.content, message.role, t("lead.assistant_name")));
    renderBrief(data.brief, false);
    show("intake");
    messagesElement.scrollTo({ top: messagesElement.scrollHeight, behavior: "instant" });
    chatInput.focus();
  }

  async function sendIntake(message) {
    const userRow = appendMessage(messagesElement, message, "user");
    const pendingRow = appendMessage(messagesElement, "", "assistant", t("lead.assistant_name"));
    pendingDots(pendingRow);
    chatSend.disabled = true;
    setStatus(chatStatus, "");
    try {
      const data = await api("/api/leads/chat", {
        method: "POST",
        body: JSON.stringify({
          message,
          conversation_id: session.conversationId,
          context_id: session.conversationId ? null : session.contextId,
          language: getLanguage(),
          scoring: session.brief?.scoring || $("#lead-scoring").value,
        }),
      });
      session.conversationId = data.conversation_id;
      pendingRow.remove();
      appendMessage(messagesElement, data.message.content, "assistant", t("lead.assistant_name"), true);
      renderBrief(data.brief, data.ready);
    } catch (error) {
      pendingRow.remove();
      userRow.remove();
      chatInput.value = message;
      resizeTextArea(chatInput);
      setStatus(chatStatus, error instanceof TypeError ? t("builder.unreachable") : error.message);
    } finally {
      chatSend.disabled = false;
      chatInput.focus();
    }
  }

  function briefRow(key, label, content) {
    const row = el("div", "lead-brief-row");
    row.dataset.key = key;
    row.append(el("dt", "", label));
    const value = el("dd");
    value.append(...[content].flat());
    row.append(value);
    return row;
  }

  function chips(values, className = "") {
    if (!values.length) return el("span", "lead-muted", t("lead.brief_open"));
    const wrap = el("span", "lead-chips");
    values.forEach((value) => wrap.append(el("span", `lead-chip ${className}`, value)));
    return wrap;
  }

  function criterionText(criterion) {
    if (criterion.kind === "number") {
      return t("lead.criterion_number", { high: criterion.high, medium: criterion.medium });
    }
    return t("lead.criterion_text", { high: criterion.high || "–", medium: criterion.medium || "–" });
  }

  function scorecardList(scorecard) {
    if (!scorecard.length) return el("span", "lead-muted", t("lead.brief_open"));
    const items = el("ul", "lead-criteria");
    scorecard.forEach((criterion) => {
      const item = el("li");
      item.append(el("strong", "", columnLabel(criterion.column)), el("span", "", criterionText(criterion)));
      items.append(item);
    });
    return items;
  }

  function renderBrief(brief, ready) {
    const previous = session.brief;
    session.brief = brief;
    session.ready = Boolean(ready && brief && brief.count);
    briefBody.replaceChildren();
    if (!brief) {
      briefTitle.textContent = t("lead.brief_empty_title");
      briefBody.append(el("p", "lead-muted", t("lead.brief_empty_copy")));
    } else {
      briefTitle.textContent = brief.title;
      const rows = el("dl", "lead-brief-list");
      const fixed = el("span", "lead-chip lead-chip-quiet", t("lead.fixed_columns"));
      rows.append(
        briefRow("description", t("lead.brief.organisations"), el("span", "", brief.description || t("lead.brief_open"))),
        briefRow("industries", t("lead.brief.industries"), chips(brief.industries)),
        briefRow("regions", t("lead.brief.regions"), chips(brief.regions)),
        briefRow("size", t("lead.brief.size"), el("span", brief.size ? "" : "lead-muted", brief.size || t("lead.brief_open"))),
        briefRow("exclude", t("lead.brief.exclude"), chips(brief.exclude || [])),
        briefRow("columns", t("lead.brief.columns"), [fixed, chips(brief.extra_columns.map((column) => column.name), "lead-chip-accent")]),
        briefRow("scorecard", t("lead.brief.scorecard"), brief.scoring === "sam_points" ? el("p", "lead-small", SAM_COPY) : scorecardList(brief.scorecard)),
        briefRow("count", t("lead.brief.count"), el("span", brief.count ? "lead-count" : "lead-muted",
          brief.count ? t("lead.count_value", { count: brief.count }) : t("lead.count_open"))),
      );
      // Show what this turn changed, so the user sees the brief follow the conversation.
      if (previous) {
        rows.querySelectorAll(".lead-brief-row").forEach((row) => {
          const key = row.dataset.key;
          const before = JSON.stringify(key === "columns" ? previous.extra_columns : previous[key]);
          const after = JSON.stringify(key === "columns" ? brief.extra_columns : brief[key]);
          if (before !== after) row.classList.add("is-changed");
        });
      }
      briefBody.append(rows);
    }
    startSearch.disabled = !session.ready || !settings.available;
    briefHint.textContent = !settings.available
      ? t(`lead.unavailable_${settings.missing || "assistant"}`)
      : session.ready ? t("lead.brief_hint_ready") : t("lead.brief_hint_waiting");
    briefHint.classList.toggle("is-ready", session.ready);
  }

  startForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = startMessage.value.trim();
    const context = startingPoints().find((item) => item.id === contextSelect.value);
    if (!message || !context) {
      if (!context) contextSelect.focus();
      return;
    }
    resetIntake(context.id, context.name);
    startMessage.value = "";
    show("intake");
    await sendIntake(message);
  });

  startMessage.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      startForm.requestSubmit();
    }
  });

  chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = chatInput.value.trim();
    if (!message) return;
    chatInput.value = "";
    resizeTextArea(chatInput);
    await sendIntake(message);
  });

  chatInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      chatForm.requestSubmit();
    }
  });
  chatInput.addEventListener("input", () => resizeTextArea(chatInput));

  startSearch.addEventListener("click", async () => {
    if (!session.ready) return;
    startSearch.disabled = true;
    try {
      const detail = await api("/api/leads/lists", {
        method: "POST",
        body: JSON.stringify({
          context_id: session.contextId,
          conversation_id: session.conversationId,
          brief: session.brief,
          language: getLanguage(),
        }),
      });
      openListDetail(detail);
    } catch (error) {
      setStatus(chatStatus, error.message);
      startSearch.disabled = false;
    }
  });

  // ------------------------------------------------------------------- the list

  async function openList(listId) {
    try {
      openListDetail(await api(`/api/leads/lists/${listId}`));
    } catch (error) {
      await loadHome();
      unavailable.textContent = error.message;
      unavailable.hidden = false;
    }
  }

  function openListDetail(detail) {
    list = detail;
    shownRows = new Set();
    renderedSignature = "";
    filter = "all";
    search.value = "";
    tableBody.replaceChildren();
    show("result");
    renderList(true);
    window.scrollTo({ top: 0, behavior: "instant" });
    schedulePoll();
  }

  function rowKey(row) {
    return row.website;
  }

  function sortedRows() {
    return [...list.rows].sort((a, b) =>
      (b.score.points ?? POINTS[b.score.level] ?? -1) - (a.score.points ?? POINTS[a.score.level] ?? -1) || a.name.localeCompare(b.name));
  }

  function renderList(first = false) {
    resultTitle.textContent = list.title;
    resultMeta.replaceChildren(
      el("span", "", list.context_name),
      ...(creator(list) ? [el("span", "", creator(list))] : []),
      el("span", "", formatDate(list.created_at)),
      el("span", "", t("lead.expires_in", { days: daysLeft(list.expires_at) })),
    );
    exportLink.href = `/api/leads/lists/${list.id}/export?language=${getLanguage()}`;
    exportLink.classList.toggle("is-disabled", !list.rows.length);
    exportLink.setAttribute("aria-disabled", String(!list.rows.length));
    renderProgress();
    // Polling returns the same list most of the time: leave the table (and the
    // keyboard focus in it) alone unless rows, scores or the status changed.
    const signature = JSON.stringify([list.id, list.status, list.found, list.brief.scorecard, list.brief.extra_columns, getLanguage()]);
    if (!first && signature === renderedSignature) return;
    renderedSignature = signature;
    renderFilters();
    renderHead();
    renderRows(first);
  }

  function renderProgress() {
    const running = list.status === "running";
    progress.hidden = !running;
    if (running) {
      const share = list.requested ? Math.min(1, list.found / list.requested) : 0;
      progressBar.style.transform = `scaleX(${Math.max(share, 0.02)})`;
      progressText.textContent = t("lead.progress", { found: list.found, requested: list.requested });
    }
    let notice = "";
    if (list.status === "failed") notice = t(list.error === "search_unavailable" ? "lead.error.search_unavailable" : "lead.error.search_failed");
    else if (list.status === "interrupted") notice = t("lead.error.interrupted");
    else if (list.status === "done" && list.found < list.requested) notice = t("lead.fewer_found", { found: list.found, requested: list.requested });
    if (list.skipped) notice = [notice, t("lead.skipped", { count: list.skipped })].filter(Boolean).join(" ");
    resultNotice.textContent = notice;
    resultNotice.hidden = !notice;
  }

  function renderFilters() {
    filters.replaceChildren();
    const options = [["all", list.rows.length], ...LEVELS.map((level) => [level, list.counts[level] || 0])];
    options.forEach(([value, count]) => {
      const button = el("button", `lead-filter lead-filter-${value}`);
      button.type = "button";
      button.setAttribute("aria-pressed", String(filter === value));
      if (value !== "all") button.append(el("span", "lead-score-dot"));
      button.append(el("span", "", value === "all" ? t("lead.filter_all") : sam() ? ({high: "A", medium: "B", low: "C"}[value]) : t(`lead.score.${value}`)), el("span", "lead-filter-count", String(count)));
      button.addEventListener("click", () => {
        filter = value;
        renderFilters();
        renderRows();
      });
      filters.append(button);
    });
  }

  function renderHead() {
    const labels = [
      t("lead.col.score"), t("lead.col.organisation"), t("lead.col.location"), t("lead.col.phone"),
      t("lead.col.email"), t("lead.col.linkedin"), ...list.brief.extra_columns.map((column) => column.name),
      ...(sam() ? Object.values(SAM_SIGNALS) : []), t("lead.col.why"), t("lead.col.sources"),
    ];
    tableHead.replaceChildren(...labels.map((label, index) => {
      const cell = el("th", index === 1 ? "lead-col-organisation" : index === 0 ? "lead-col-score" : "", label);
      cell.scope = "col";
      return cell;
    }));
  }

  function factCell(fact, render = (value) => el("span", "", value)) {
    const cell = el("td");
    if (fact && fact.value) cell.append(render(fact.value));
    else {
      const unknown = el("span", "lead-unknown", "—");
      unknown.title = t("lead.not_found");
      cell.append(unknown);
    }
    return cell;
  }

  function leadRowElement(row, index) {
    const tr = el("tr", "lead-row");
    tr.tabIndex = 0;
    tr.setAttribute("aria-label", t("lead.row_aria", { name: row.name }));
    const scoreCell = el("td", "lead-col-score");
    scoreCell.append(rowPill(row));
    const organisation = el("td", "lead-col-organisation");
    organisation.append(el("span", "lead-name", row.name), externalLink(row.website, domain(row.website), "lead-domain"));
    const location = el("td");
    const place = [row.city.value, row.country.value].filter(Boolean).join(" · ");
    location.append(place ? el("span", "", place) : Object.assign(el("span", "lead-unknown", "—"), { title: t("lead.not_found") }));
    const phone = factCell(row.phone, (value) => {
      const link = el("a", "lead-contact", value);
      link.href = `tel:${value.replace(/[^\d+]/g, "")}`;
      link.addEventListener("click", (event) => event.stopPropagation());
      return link;
    });
    const email = factCell(row.email, (value) => {
      const link = el("a", "lead-contact", value);
      link.href = `mailto:${value}`;
      link.addEventListener("click", (event) => event.stopPropagation());
      return link;
    });
    const linkedin = el("td");
    if (row.linkedin) {
      const link = externalLink(row.linkedin, t("lead.linkedin_people"), "lead-linkedin");
      link.setAttribute("aria-label", t("lead.linkedin_aria", { name: row.name }));
      linkedin.append(link);
    } else {
      linkedin.append(Object.assign(el("span", "lead-unknown", "—"), { title: t("lead.not_found") }));
    }
    const extras = list.brief.extra_columns.map((column) => factCell(row.extra[column.name], (value) => el("span", "lead-extra", value)));
    const why = el("td", "lead-col-why");
    why.append(el("span", "lead-why", row.why_fits));
    const sources = el("td", "lead-col-sources");
    const sourceButton = el("button", "lead-sources-button", String(row.sources.length));
    sourceButton.type = "button";
    sourceButton.setAttribute("aria-label", t("lead.sources_aria", { count: row.sources.length, name: row.name }));
    sourceButton.addEventListener("click", (event) => { event.stopPropagation(); openRowDrawer(row, sourceButton); });
    sources.append(sourceButton);
    tr.append(scoreCell, organisation, location, phone, email, linkedin, ...extras, ...(sam() ? Object.keys(SAM_SIGNALS).map((key) => factCell(row.signals?.[key])) : []), why, sources);
    tr.addEventListener("click", () => openRowDrawer(row, tr));
    tr.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openRowDrawer(row, tr);
      }
    });
    if (!shownRows.has(rowKey(row))) {
      tr.classList.add("is-new");
      tr.style.setProperty("--stagger", `${Math.min(index, 8) * 40}ms`);
    }
    return tr;
  }

  function skeletonRow(columns) {
    const tr = el("tr", "lead-skeleton");
    tr.setAttribute("aria-hidden", "true");
    for (let index = 0; index < columns; index += 1) {
      const cell = el("td");
      cell.append(el("span", "lead-skeleton-bar"));
      tr.append(cell);
    }
    return tr;
  }

  function renderRows(first = false) {
    const query = search.value.trim().toLocaleLowerCase();
    const rows = sortedRows().filter((row) =>
      (filter === "all" || row.score.level === filter)
      && (!query || `${row.name} ${row.city.value || ""} ${row.website}`.toLocaleLowerCase().includes(query)));
    let added = 0;
    const elements = rows.map((row) => {
      const element = leadRowElement(row, shownRows.has(rowKey(row)) ? 0 : added++);
      return element;
    });
    // The first render of a finished list appears at once; rows that arrive while
    // searching slide in, so the user sees the list grow.
    if (first && list.status !== "running") elements.forEach((element) => element.classList.remove("is-new"));
    const columnCount = 8 + list.brief.extra_columns.length + (sam() ? 4 : 0);
    const skeletons = list.status === "running" && filter === "all" && !query
      ? Array.from({ length: Math.min(3, Math.max(0, list.requested - list.found)) }, () => skeletonRow(columnCount))
      : [];
    tableBody.replaceChildren(...elements, ...skeletons);
    list.rows.forEach((row) => shownRows.add(rowKey(row)));
    const nothing = !rows.length && !skeletons.length;
    emptyState.hidden = !nothing;
    if (nothing) {
      emptyState.replaceChildren(el("h2", "", list.rows.length ? t("lead.no_match_title") : t("lead.no_rows_title")),
        el("p", "", list.rows.length ? t("lead.no_match_copy") : t("lead.no_rows_copy")));
    }
  }

  search.addEventListener("input", () => renderRows());

  let exportBusy = false;
  const exportStatus = el("p", "lead-export-status");
  exportStatus.setAttribute("role", "status");
  exportLink.after(exportStatus);
  exportLink.addEventListener("click", async (event) => {
    event.preventDefault();
    if (!list || !list.rows.length || exportBusy) return;
    exportBusy = true;
    exportLink.setAttribute("aria-disabled", "true");
    exportStatus.textContent = t("lead.export_preparing");
    try {
      const response = await fetch(exportLink.href, { credentials: "same-origin", headers: { "X-SIP-Language": getLanguage() } });
      const type = response.headers.get("content-type") || "";
      if (!response.ok || !type.includes("spreadsheetml.sheet")) throw new Error(t("lead.export_failed"));
      const bytes = await response.arrayBuffer();
      const filename = /filename="([^"]+)"/.exec(response.headers.get("content-disposition") || "")?.[1] || "leads.xlsx";
      const url = URL.createObjectURL(new Blob([bytes], { type: "application/octet-stream" }));
      const download = document.createElement("a");
      download.href = url;
      download.download = filename;
      document.body.appendChild(download);
      download.click();
      download.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 60000);
      exportStatus.textContent = t("lead.export_started");
    } catch (error) {
      exportStatus.textContent = t("lead.export_failed");
    } finally {
      exportBusy = false;
      exportLink.setAttribute("aria-disabled", String(!list?.rows.length));
    }
  });

  function stopPolling() {
    window.clearTimeout(pollTimer);
    pollTimer = 0;
  }

  function schedulePoll() {
    stopPolling();
    if (!list || list.status !== "running") return;
    pollTimer = window.setTimeout(async () => {
      // Stop when the user left the list; opening it again restarts polling.
      if (result.hidden || $("#lead-view").hidden || !list) return;
      try {
        const fresh = await api(`/api/leads/lists/${list.id}`);
        if (!list || fresh.id !== list.id) return;
        list = fresh;
        renderList();
      } catch {
        // A missed poll is retried; the list keeps what it showed.
      }
      schedulePoll();
    }, POLL_MS);
  }

  // ------------------------------------------------------------------- drawer

  function openDrawer(kicker, title, trigger) {
    drawerReturnFocus = trigger;
    drawerKicker.replaceChildren(...[kicker].flat());
    drawerTitle.textContent = title;
    drawerBody.replaceChildren();
    drawerFooter.replaceChildren();
    drawer.hidden = false;
    $("#lead-drawer-close").focus();
  }

  function closeDrawer(restoreFocus = true) {
    if (drawer.hidden) return;
    drawer.hidden = true;
    if (restoreFocus) drawerReturnFocus?.focus();
  }

  // A fixed panel inside the animated view would be placed relative to the view;
  // like the source panel it lives directly under <body>.
  document.body.append(drawer);
  document.querySelectorAll(".nav-item, .brand-link").forEach((item) => item.addEventListener("click", () => closeDrawer(false)));
  $("#lead-drawer-close").addEventListener("click", () => closeDrawer());
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !drawer.hidden) closeDrawer();
  });

  function factLine(label, fact, render = (value) => el("span", "", value)) {
    const row = el("div", "lead-fact");
    row.append(el("dt", "", label));
    const value = el("dd");
    if (fact && fact.value) {
      value.append(render(fact.value));
      if (fact.source) value.append(externalLink(fact.source, sourceLabel(fact.source), "lead-fact-source"));
    } else {
      value.append(el("span", "lead-muted", t("lead.not_found")));
    }
    row.append(value);
    return row;
  }

  function openRowDrawer(row, trigger) {
    openDrawer(rowPill(row), row.name, trigger);
    if (row.why_fits) {
      const why = el("section", "lead-drawer-section");
      why.append(el("h3", "", t("lead.col.why")), el("p", "lead-drawer-why", row.why_fits));
      drawerBody.append(why);
    }
    const facts = el("section", "lead-drawer-section");
    const list_ = el("dl", "lead-facts");
    list_.append(
      factLine(t("lead.col.city"), row.city),
      factLine(t("lead.col.country"), row.country),
      factLine(t("lead.col.phone"), row.phone),
      factLine(t("lead.col.email"), row.email),
      ...list.brief.extra_columns.map((column) => factLine(column.name, row.extra[column.name])),
      ...(sam() ? Object.entries(SAM_SIGNALS).map(([key, label]) => factLine(label, row.signals?.[key])) : []),
    );
    facts.append(el("h3", "", t("lead.facts")), list_);
    drawerBody.append(facts);
    if (sam()) {
      const section = el("section", "lead-drawer-section");
      section.append(el("h3", "", "SAM-punten"));
      Object.entries(row.score.blocks || {}).forEach(([label, points]) => section.append(el("p", "", `${label}: ${points} punten`)));
      Object.entries(row.score.components || {}).forEach(([label, points]) => section.append(el("p", "lead-small", `${label}: ${points}`)));
      if (row.score.unknown?.length) section.append(el("p", "lead-muted", `Onbekend: ${row.score.unknown.join(", ")}. Levert 0 punten op.`));
      section.append(el("p", "lead-small", SAM_COPY));
      drawerBody.append(section);
    }

    if (row.score.criteria.length) {
      const score = el("section", "lead-drawer-section");
      const items = el("ul", "lead-score-breakdown");
      row.score.criteria.forEach((criterion) => {
        const item = el("li");
        const label = el("span", "lead-breakdown-label");
        label.append(el("strong", "", columnLabel(criterion.column)), el("span", "lead-muted", criterion.value || t("lead.not_found")));
        item.append(label, criterion.level === "unknown" ? el("span", "lead-score lead-score-none", t("lead.score.unknown")) : scorePill(criterion.level));
        items.append(item);
      });
      score.append(el("h3", "", t("lead.score_why")), items);
      if (row.score.criteria.some((criterion) => criterion.level === "unknown")) {
        score.append(el("p", "lead-muted lead-small", t("lead.unknown_caps")));
      }
      drawerBody.append(score);
    }

    const contact = el("section", "lead-drawer-section");
    contact.append(el("h3", "", t("lead.contact_person")));
    contact.append(el("p", "lead-muted lead-small", t("lead.contact_person_copy")));
    if (row.linkedin) contact.append(externalLink(row.linkedin, t("lead.linkedin_people_long"), "secondary-button lead-drawer-linkedin"));
    drawerBody.append(contact);

    const sources = el("section", "lead-drawer-section");
    const links = el("ul", "lead-source-list");
    row.sources.forEach((url) => {
      const item = el("li");
      item.append(externalLink(url, sourceLabel(url)));
      links.append(item);
    });
    sources.append(el("h3", "", t("lead.col.sources")), links);
    drawerBody.append(sources);
    drawerFooter.append(externalLink(row.website, t("lead.open_website"), "primary-button"));
  }

  // The scorecard can change after the search: the server rescores the stored facts.
  function criterionEditor(criterion, columns) {
    const row = el("div", "lead-criterion");
    const column = el("select");
    column.setAttribute("aria-label", t("lead.criterion_column"));
    columns.forEach((name) => column.add(new Option(columnLabel(name), name)));
    column.value = criterion.column;
    const kind = el("select");
    kind.setAttribute("aria-label", t("lead.criterion_kind"));
    kind.add(new Option(t("lead.kind_number"), "number"));
    kind.add(new Option(t("lead.kind_text"), "text"));
    kind.value = criterion.kind;
    const high = el("input");
    const medium = el("input");
    const highLabel = el("label", "lead-criterion-field");
    const mediumLabel = el("label", "lead-criterion-field");
    const sync = () => {
      const number = kind.value === "number";
      [high, medium].forEach((input) => {
        input.type = number ? "number" : "text";
        input.inputMode = number ? "numeric" : "text";
      });
      highLabel.firstChild.textContent = t(number ? "lead.high_from" : "lead.high_words");
      mediumLabel.firstChild.textContent = t(number ? "lead.medium_from" : "lead.medium_words");
    };
    high.value = criterion.high;
    medium.value = criterion.medium;
    highLabel.append(el("span"), high);
    mediumLabel.append(el("span"), medium);
    kind.addEventListener("change", sync);
    sync();
    const remove = deleteButton(t("lead.remove_criterion"), () => {
      row.remove();
      syncAddButton();
    });
    const top = el("div", "lead-criterion-top");
    top.append(column, kind, remove);
    row.append(top, highLabel, mediumLabel);
    row.read = () => ({ column: column.value, kind: kind.value, high: high.value.trim(), medium: medium.value.trim() });
    return row;
  }

  let syncAddButton = () => {};

  function openScorecardDrawer(trigger) {
    openDrawer(t("lead.scorecard"), list.title, trigger);
    if (sam()) {
      drawerBody.append(el("p", "", SAM_COPY));
      return;
    }
    const columns = ["country", "city", ...list.brief.extra_columns.map((column) => column.name)];
    drawerBody.append(el("p", "lead-muted lead-small", t("lead.scorecard_copy")));
    const editors = el("div", "lead-criteria-editor");
    list.brief.scorecard.forEach((criterion) => editors.append(criterionEditor(criterion, columns)));
    const add = el("button", "secondary-button lead-add-criterion", t("lead.add_criterion"));
    add.type = "button";
    syncAddButton = () => { add.disabled = editors.children.length >= 4; };
    add.addEventListener("click", () => {
      editors.append(criterionEditor({ column: columns[columns.length - 1], kind: "number", high: "", medium: "" }, columns));
      syncAddButton();
      editors.lastElementChild.querySelector("select").focus();
    });
    syncAddButton();
    const status = el("p", "status");
    status.setAttribute("role", "status");
    drawerBody.append(editors, add, status);
    const save = el("button", "primary-button", t("lead.save_scorecard"));
    save.type = "button";
    const cancel = el("button", "secondary-button", t("lead.cancel"));
    cancel.type = "button";
    cancel.addEventListener("click", () => closeDrawer());
    save.addEventListener("click", async () => {
      save.disabled = true;
      try {
        const scorecard = [...editors.children].map((editor) => editor.read());
        list = await api(`/api/leads/lists/${list.id}/scorecard`, { method: "PUT", body: JSON.stringify({ scorecard }) });
        renderList();
        closeDrawer();
      } catch (error) {
        setStatus(status, error.message);
        save.disabled = false;
      }
    });
    drawerFooter.append(save, cancel);
  }

  $("#lead-edit-scorecard").addEventListener("click", (event) => openScorecardDrawer(event.currentTarget));

  // ------------------------------------------------------------------- navigation

  $("#lead-back-from-intake").addEventListener("click", () => openLeadFinder());
  $("#lead-back-from-result").addEventListener("click", () => openLeadFinder());
  $("#nav-lead").addEventListener("click", () => openLeadFinder());

  // Re-render translated, generated text when the language changes.
  $("#language-switcher")?.addEventListener("change", () => setTimeout(() => {
    if (!result.hidden && list) renderList();
    if (!intake.hidden) renderBrief(session.brief, session.ready);
    if (!home.hidden && !$("#lead-view").hidden) loadHome();
  }));
})();
