// Version history of a Business Context: every saved version with who, when and how,
// what changed per field, and restore (Product Owner and admin). Uses the helpers of
// app.js (api, t, formatDate, renderContextChanges, openContext, ...).
(() => {
  const panel = document.querySelector("#history-panel");
  const title = document.querySelector("#history-panel-title");
  const body = document.querySelector("#history-panel-body");
  const button = document.querySelector("#review-history");
  let contextId = null;
  let returnFocus = null;

  const mayRestore = () => currentRole === "admin" || currentRole === "product_owner";

  function el(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined && text !== null) element.textContent = text;
    return element;
  }

  function when(value) {
    const date = new Date(`${value.replace(" ", "T")}Z`);
    return Number.isNaN(date.valueOf())
      ? value
      : new Intl.DateTimeFormat(getLanguage(), { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(date);
  }

  function how(version) {
    const source = t(`history.source.${version.source}`);
    return version.restored_from ? `${source} · ${t("history.restored_from", { version: version.restored_from })}` : source;
  }

  function meta(version) {
    return [when(version.created_at), version.changed_by ? t("history.by", { name: version.changed_by }) : null, how(version)]
      .filter(Boolean).join(" · ");
  }

  async function showList() {
    body.replaceChildren(el("p", "history-loading", t("history.loading")));
    let versions;
    try {
      versions = await api(`/api/contexts/${contextId}/versions`);
    } catch (error) {
      body.replaceChildren(el("p", "status", error.message));
      return;
    }
    const list = el("ol", "history-list");
    versions.forEach((version, index) => {
      const item = el("li");
      const open = el("button", "history-item");
      open.type = "button";
      const head = el("span", "history-item-head");
      head.append(el("strong", "", t("history.version", { version: version.version })));
      if (index === 0) head.append(el("span", "history-current", t("history.current")));
      open.append(head, el("span", "history-item-meta", meta(version)));
      const changed = version.changed_fields.length
        ? t("history.changed", { fields: version.changed_fields.map(contextFieldLabel).join(", ") })
        : t(version.version === 1 ? "history.first" : "history.no_field_changes");
      open.append(el("span", "history-item-changes", changed));
      open.addEventListener("click", () => showVersion(version.version, index === 0));
      item.append(open);
      list.append(item);
    });
    body.replaceChildren(list);
  }

  async function showVersion(number, isCurrent) {
    let version;
    try {
      version = await api(`/api/contexts/${contextId}/versions/${number}`);
    } catch (error) {
      body.replaceChildren(el("p", "status", error.message));
      return;
    }
    const back = el("button", "text-button", t("history.back"));
    back.type = "button";
    back.addEventListener("click", showList);
    const heading = el("h3", "history-version-title", t("history.version", { version: version.version }));
    const changes = el("div", "context-changes");
    renderContextChanges(version.changes, changes);
    if (version.changed_fields.includes("status")) {
      changes.prepend(el("p", "history-status-change", t("history.status_now", { status: t(`history.status.${version.status}`) })));
    }
    const parts = [back, heading, el("p", "history-item-meta", meta(version)), changes];
    if (!isCurrent && mayRestore()) {
      const restore = el("button", "secondary-button history-restore", t("history.restore"));
      restore.type = "button";
      restore.addEventListener("click", () => confirmRestore(version.version));
      parts.push(restore);
    }
    body.replaceChildren(...parts);
    body.scrollTop = 0;
  }

  function confirmRestore(number) {
    pendingDelete = {
      kind: "restore",
      id: null,
      action: async () => {
        await api(`/api/contexts/${contextId}/versions/${number}/restore`, { method: "POST" });
        await openContext(contextId);
        open(returnFocus);
      },
    };
    deleteTitle.textContent = t("history.restore_title", { version: number });
    deleteDescription.textContent = t("history.restore_description", { version: number });
    const confirmButton = document.querySelector("#confirm-delete");
    confirmButton.textContent = t("history.restore");
    // Restoring removes nothing, so not the red delete style.
    confirmButton.className = "primary-button";
    deleteDialog.addEventListener("close", () => { confirmButton.className = "danger-button"; }, { once: true });
    deleteDialog.showModal();
  }

  function open(trigger) {
    if (!contextId) return;
    returnFocus = trigger;
    title.textContent = document.querySelector("#context-form").elements.namedItem("name").value || "";
    panel.hidden = false;
    document.querySelector("#history-panel-close").focus();
    showList();
  }

  function close() {
    if (panel.hidden) return;
    panel.hidden = true;
    returnFocus?.focus();
  }

  button.addEventListener("click", (event) => open(event.currentTarget));
  document.querySelector("#history-panel-close").addEventListener("click", close);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") close();
  });
  document.querySelectorAll(".nav-item, .brand-link").forEach((item) => item.addEventListener("click", () => { panel.hidden = true; }));

  window.contextHistory = {
    // A saved context has a history; a proposal from a conversation does not yet.
    syncReview(id) {
      contextId = id || null;
      button.hidden = !contextId;
      panel.hidden = true;
    },
  };
})();
