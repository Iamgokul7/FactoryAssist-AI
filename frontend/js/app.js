/* FactoryAssist AI — dashboard behaviour (vanilla JS, no dependencies) */
(() => {
  "use strict";

  const SUGGESTIONS = [
    "What is the recommended coolant concentration for the TX-200 CNC turning centre?",
    "The machine is showing alarm AL-104. What does it mean and what should the operator do?",
    "Who is allowed to remove a lockout lock from a machine?",
    "What is the outer diameter tolerance for the BH-220 bearing housing?",
    "How often should spindle runout be checked, and who does it?",
  ];

  const VIEWS = {
    dashboard: {
      title: "Manufacturing dashboard",
      subtitle:
        "Grounded answers from the plant's active SOPs, maintenance manuals and quality procedures.",
    },
    assistant: {
      title: "Manufacturing AI Assistant",
      subtitle:
        "Ask about safety procedures, machine maintenance or quality standards.",
    },
    knowledge: {
      title: "Knowledge base",
      subtitle: "The controlled documents behind every answer.",
    },
    documents: {
      title: "Document management",
      subtitle:
        "Upload, review, activate and archive controlled SOPs. Only active revisions are searchable.",
    },
    about: {
      title: "System information",
      subtitle: "Runtime configuration, API surface and known limitations.",
    },
  };

  const state = { status: null, busy: false };

  // Management state is kept separate from the chat so a signed-out visitor
  // still gets the assistant: only management routes require a session.
  const management = {
    user: null,
    csrf: null,
    documents: [],
    stats: null,
    statusFilter: "",
    search: "",
    meta: null,
    audit: [],
    file: null,
    uploading: false,
  };

  const ROLE_LABELS = {
    admin: "Administrator",
    sop_manager: "SOP Manager",
    employee: "Employee",
  };

  const STATUS_PILL = {
    active: "status-active",
    pending_review: "status-pending",
    processing: "status-processing",
    archived: "status-archived",
    rejected: "status-rejected",
    failed: "status-failed",
  };

  // `/api/status` reports whether the configured Gemini model is actually
  // usable, not just whether a key exists. The server caches the probe.
  const MODEL_BADGES = {
    ready: { badge: "AI service ready", variant: "ok" },
    not_configured: { badge: "AI key missing", variant: "warn" },
    unavailable: { badge: "AI model unavailable", variant: "danger" },
    unauthorized: { badge: "AI key rejected", variant: "danger" },
    unknown: { badge: "AI status unverified", variant: "warn" },
  };

  const MODEL_KPI = {
    ready: "Ready",
    not_configured: "Not configured",
    unavailable: "Unavailable",
    unauthorized: "Key rejected",
    unknown: "Unverified",
  };

  function modelState(gemini) {
    if (!gemini || !gemini.configured) return "not_configured";
    return MODEL_BADGES[gemini.model_status] ? gemini.model_status : "unknown";
  }

  const $ = (id) => document.getElementById(id);
  const chatLog = $("chat-log");
  const emptyState = $("chat-empty");
  const input = $("question-input");
  const sendBtn = $("send-btn");
  const sidebar = $("sidebar");
  const scrim = $("scrim");

  const esc = (value) =>
    String(value ?? "").replace(
      /[&<>"']/g,
      (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );

  /* ---------------- navigation ---------------- */

  function setView(name) {
    const view = VIEWS[name] ? name : "dashboard";
    document.querySelectorAll(".view").forEach((section) => {
      section.hidden = section.id !== `view-${view}`;
    });
    document.querySelectorAll(".nav-item").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.view === view);
    });
    $("page-title").textContent = VIEWS[view].title;
    $("page-subtitle").textContent = VIEWS[view].subtitle;
    closeDrawer();
    if (view === "assistant") setTimeout(() => input.focus(), 60);
    if (view === "documents" && canManage()) {
      loadDocumentMeta();
      loadDocuments();
      if (isAdmin()) loadAudit();
    }
  }

  function openDrawer() {
    sidebar.classList.add("is-open");
    scrim.hidden = false;
  }

  function closeDrawer() {
    sidebar.classList.remove("is-open");
    scrim.hidden = true;
  }

  /* ---------------- status ---------------- */

  async function loadStatus() {
    try {
      const response = await fetch("/api/status", { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`Status request failed (${response.status})`);
      const status = await response.json();
      state.status = status;
      renderStatus(status);
    } catch (error) {
      renderStatusFailure();
    }
  }

  function renderStatus(status) {
    const gemini = status.gemini || {};
    const store = status.vector_store || {};
    const corpus = status.corpus || {};
    const activeDocs = corpus.active_documents || [];
    const archivedDocs = corpus.archived_documents || [];

    $("sidebar-version").textContent = `v${status.version || "1.0.0"} · stage 7`;

    // top badges
    const model = modelState(gemini);
    const modelBroken = model === "unavailable" || model === "unauthorized";
    const modelBadge = MODEL_BADGES[model];
    setBadge("badge-ai", modelBadge.badge, modelBadge.variant);
    $("badge-ai").title = gemini.model_detail || "";
    if (!store.available) {
      setBadge("badge-index", "Index unavailable", "danger");
    } else if (status.index_ready) {
      setBadge("badge-index", `${store.indexed_chunks} chunks indexed`, "ok");
    } else {
      setBadge("badge-index", "Index empty", "warn");
    }

    // sidebar status
    const ready =
      gemini.configured && store.available && status.index_ready && !modelBroken;
    const chip = $("sidebar-status");
    chip.innerHTML = `<span class="dot ${ready ? "dot-ok" : "dot-warn"}"></span><span>${
      ready ? "System ready" : "Setup required"
    }</span>`;

    // KPIs
    $("kpi-docs").textContent = corpus.active_document_count ?? activeDocs.length;
    $("kpi-docs-hint").textContent = `${archivedDocs.length} archived revision${archivedDocs.length === 1 ? "" : "s"} kept for reference`;
    $("kpi-chunks").textContent = store.available ? store.indexed_chunks ?? 0 : "—";
    $("kpi-chunks-hint").textContent = store.available
      ? status.index_ready
        ? `Collection ${store.collection}`
        : "Run the ingestion command to index"
      : "Vector store unavailable";
    $("kpi-revisions").textContent = Object.keys(corpus.active_revisions || {}).length;
    $("kpi-ai").textContent = MODEL_KPI[model];
    $("kpi-ai-hint").textContent = modelBroken
      ? gemini.model_detail || "Check the Gemini configuration"
      : model === "ready"
      ? gemini.generation_model || "Gemini"
      : model === "not_configured"
      ? "Add GEMINI_API_KEY to .env"
      : gemini.generation_model || "Gemini";

    // chat context
    const dot = $("chat-dot");
    dot.className = `live-dot ${
      status.index_ready && gemini.configured && !modelBroken ? "is-ready" : "is-warn"
    }`;
    $("chat-context").textContent = !gemini.configured
      ? "AI key not configured — chat is disabled until a key is added"
      : modelBroken
      ? gemini.model_detail || "The configured AI model is unavailable"
      : !store.available
      ? "Document index unavailable"
      : !status.index_ready
      ? "No chunks indexed yet — run the ingestion command"
      : `${activeDocs.length} documents · ${store.indexed_chunks} chunks indexed`;

    renderDashboardDocuments(activeDocs);
    renderKnowledgeBase(activeDocs, archivedDocs);
    renderConfiguration(status, gemini, store, corpus);
  }

  function setBadge(id, text, variant) {
    const badge = $(id);
    badge.textContent = text;
    badge.className = `badge badge-${variant}`;
  }

  function renderStatusFailure() {
    setBadge("badge-ai", "Status unavailable", "danger");
    setBadge("badge-index", "Status unavailable", "danger");
    $("sidebar-status").innerHTML =
      '<span class="dot dot-warn"></span><span>Backend unreachable</span>';
    $("kpi-docs").textContent = $("kpi-chunks").textContent = $("kpi-revisions").textContent = "—";
    $("kpi-ai").textContent = "Unknown";
    $("kpi-ai-hint").textContent = "Could not reach /api/status";
    $("chat-context").textContent = "Backend unreachable";
    const message = '<tr><td colspan="7" class="table-empty">Could not load status from the server.</td></tr>';
    $("dashboard-documents").innerHTML = '<tr><td colspan="6" class="table-empty">Could not load documents.</td></tr>';
    $("kb-documents").innerHTML = message;
    $("kb-archived").innerHTML = '<tr><td colspan="5" class="table-empty">Could not load archive.</td></tr>';
  }

  function renderDashboardDocuments(documents) {
    const body = $("dashboard-documents");
    if (!documents.length) {
      body.innerHTML =
        '<tr><td colspan="6" class="table-empty">No active documents processed yet.</td></tr>';
      return;
    }
    body.innerHTML = documents
      .map(
        (doc) => `
        <tr>
          <td><span class="code-chip">${esc(doc.document_code)}</span></td>
          <td class="cell-strong">${esc(doc.document_title)}</td>
          <td>Rev ${esc(doc.revision)}</td>
          <td>${esc(doc.page_count)}</td>
          <td>${esc(doc.chunk_count)}</td>
          <td><span class="status-pill status-active">Active</span></td>
        </tr>`
      )
      .join("");
  }

  function renderKnowledgeBase(active, archived) {
    const activeBody = $("kb-documents");
    activeBody.innerHTML = active.length
      ? active
          .map(
            (doc) => `
        <tr>
          <td><span class="code-chip">${esc(doc.document_code)}</span></td>
          <td class="cell-strong">${esc(doc.document_title)}</td>
          <td>Rev ${esc(doc.revision)}</td>
          <td>${esc(doc.page_count)}</td>
          <td>${esc(doc.chunk_count)}</td>
          <td>${esc(doc.effective_date || "—")}</td>
          <td>${esc(doc.source_filename)}</td>
        </tr>`
          )
          .join("")
      : '<tr><td colspan="7" class="table-empty">No active documents processed yet.</td></tr>';

    const archivedBody = $("kb-archived");
    archivedBody.innerHTML = archived.length
      ? archived
          .map(
            (doc) => `
        <tr>
          <td><span class="code-chip">${esc(doc.document_code)}</span></td>
          <td class="cell-strong">${esc(doc.document_title)}</td>
          <td>Rev ${esc(doc.revision)}</td>
          <td>${esc(doc.page_count)}</td>
          <td>${esc(doc.superseded_by_document_id || "—")}</td>
        </tr>`
          )
          .join("")
      : '<tr><td colspan="5" class="table-empty">No archived revisions.</td></tr>';
  }

  function renderConfiguration(status, gemini, store, corpus) {
    $("cfg-generation").textContent = gemini.generation_model || "—";
    const model = modelState(gemini);
    const availability = $("cfg-model-status");
    availability.textContent =
      model === "ready"
        ? "Available"
        : MODEL_KPI[model] || "Not verified";
    availability.title = gemini.model_detail || "";
    $("cfg-embedding").textContent = gemini.embedding_model || "—";
    $("cfg-collection").textContent = store.collection || "—";
    const retrieval = status.retrieval || {};
    $("cfg-topk").textContent = `Top ${retrieval.top_k ?? "—"} chunks`;
    $("cfg-similarity").textContent = retrieval.min_similarity ?? "—";
    $("cfg-manifest").textContent = corpus.generated_at
      ? new Date(corpus.generated_at).toLocaleString()
      : "not generated";
    $("config-callout").hidden = Boolean(gemini.configured);
  }

  /* ---------------- chips ---------------- */

  function buildChips(container, includeInChat) {
    if (!container) return;
    container.innerHTML = "";
    SUGGESTIONS.forEach((question) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "chip";
      chip.textContent = question;
      chip.addEventListener("click", () => {
        if (includeInChat) setView("assistant");
        ask(question);
      });
      container.appendChild(chip);
    });
  }

  /* ---------------- chat ---------------- */

  function showEmptyState(show) {
    emptyState.hidden = !show;
  }

  function scrollToLatest() {
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  function appendUserMessage(text) {
    const row = document.createElement("div");
    row.className = "msg msg-user";
    row.innerHTML = `<div class="bubble">${esc(text)}</div>`;
    chatLog.appendChild(row);
    scrollToLatest();
  }

  function appendLoading() {
    const row = document.createElement("div");
    row.className = "msg msg-assistant";
    row.innerHTML = `
      <div class="msg-stack">
        <div class="bubble">
          <span class="typing" aria-label="Searching the documents"><span></span><span></span><span></span></span>
        </div>
      </div>`;
    chatLog.appendChild(row);
    scrollToLatest();
    return row;
  }

  function answerLabel(status) {
    if (status === "answered") return "Answered from documents";
    if (status === "insufficient_evidence") return "No matching evidence";
    if (status === "not_configured") return "AI service not configured";
    if (status === "invalid_question") return "Check the question";
    return "Service error";
  }

  function appendAssistantMessage(data) {
    const status = data.status || "error";
    const variant =
      status === "answered"
        ? ""
        : status === "insufficient_evidence"
        ? " is-fallback"
        : " is-error";

    const sources = Array.isArray(data.sources) ? data.sources : [];
    const sourceHtml = sources.length
      ? `<div class="sources">${sources
          .map(
            (source) => `
          <div class="source-card">
            <p class="source-title">${esc(source.document_title)}</p>
            <div class="source-meta">
              <span class="meta-strong">${esc(source.document_code)}</span>
              <span>Rev ${esc(source.revision)}</span>
              <span>Page ${esc(source.page_number)}</span>
              <span>${esc(source.source_filename)}</span>
            </div>
          </div>`
          )
          .join("")}</div>`
      : "";

    const row = document.createElement("div");
    row.className = "msg msg-assistant";
    row.innerHTML = `
      <div class="msg-stack">
        <div class="bubble${variant}">
          <p class="msg-label">${esc(answerLabel(status))}</p>
          ${esc(data.answer)}
        </div>
        ${sourceHtml}
      </div>`;
    chatLog.appendChild(row);
    scrollToLatest();
  }

  function appendErrorMessage(message) {
    const row = document.createElement("div");
    row.className = "msg msg-assistant";
    row.innerHTML = `
      <div class="msg-stack">
        <div class="bubble is-error">
          <p class="msg-label">Connection problem</p>
          ${esc(message)}
        </div>
      </div>`;
    chatLog.appendChild(row);
    scrollToLatest();
  }

  function setBusy(busy) {
    state.busy = busy;
    sendBtn.disabled = busy;
    input.disabled = busy;
    if (!busy) input.focus();
  }

  async function ask(question) {
    const text = String(question || "").trim();
    if (!text || state.busy) return;

    showEmptyState(false);
    appendUserMessage(text);
    const loading = appendLoading();
    setBusy(true);
    input.value = "";
    autosize();

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ question: text }),
      });

      if (!response.ok) {
        let detail = "";
        try {
          const payload = await response.json();
          if (payload && payload.detail) detail = String(payload.detail);
        } catch (_) {
          /* response had no JSON body */
        }
        throw new Error(detail || `Request failed with status ${response.status}.`);
      }

      const data = await response.json();
      loading.remove();
      appendAssistantMessage(data);
      if (data.status === "not_configured" || data.status === "error") {
        loadStatus();
      }
    } catch (error) {
      loading.remove();
      appendErrorMessage(
        error instanceof TypeError
          ? "Could not reach the server. Check that the application is still running."
          : error.message
      );
    } finally {
      setBusy(false);
    }
  }

  /* ---------------- composer ---------------- */

  function autosize() {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 140)}px`;
  }

  input.addEventListener("input", autosize);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      $("composer").requestSubmit();
    }
  });

  $("composer").addEventListener("submit", (event) => {
    event.preventDefault();
    ask(input.value);
  });

  $("clear-chat").addEventListener("click", () => {
    chatLog.querySelectorAll(".msg").forEach((node) => node.remove());
    showEmptyState(true);
    input.value = "";
    autosize();
    input.focus();
  });

  /* ---------------- document management: API helpers ---------------- */

  function canManage() {
    return Boolean(management.user && management.user.can_manage_documents);
  }

  function isAdmin() {
    return Boolean(management.user && management.user.can_manage_users);
  }

  function formatDetail(detail) {
    if (!detail) return "The request could not be completed.";
    if (Array.isArray(detail)) {
      return detail.map((item) => item.msg || JSON.stringify(item)).join("; ");
    }
    if (typeof detail === "object") return detail.message || JSON.stringify(detail);
    return String(detail);
  }

  async function apiFetch(path, options = {}) {
    const method = (options.method || "GET").toUpperCase();
    const headers = Object.assign({ Accept: "application/json" }, options.headers || {});
    if (management.csrf && ["POST", "PATCH", "PUT", "DELETE"].includes(method)) {
      headers["X-CSRF-Token"] = management.csrf;
    }
    const response = await fetch(path, {
      ...options,
      method,
      headers,
      credentials: "same-origin",
    });

    let payload = null;
    try {
      payload = await response.json();
    } catch (_) {
      /* empty or non-JSON body */
    }

    if (!response.ok) {
      const message = payload && payload.detail
        ? formatDetail(payload.detail)
        : `Request failed (${response.status}).`;
      const error = new Error(message);
      error.status = response.status;
      throw error;
    }
    return payload;
  }

  /* ---------------- session ---------------- */

  function applySession(payload) {
    management.user = payload && payload.user ? payload.user : null;
    management.csrf = payload && payload.csrf_token ? payload.csrf_token : null;

    const signedIn = Boolean(management.user);
    $("login-btn").hidden = signedIn;
    $("logout-btn").hidden = !signedIn;

    const chip = $("auth-user");
    chip.hidden = !signedIn;
    if (signedIn) {
      const role = ROLE_LABELS[management.user.role] || management.user.role;
      chip.innerHTML = `<svg><use href="#i-user"/></svg><span>${esc(
        management.user.full_name || management.user.username
      )} · ${esc(role)}</span>`;
      chip.title = `${management.user.username} · ${role}`;
    } else {
      chip.innerHTML = "";
    }

    $("nav-documents").hidden = !canManage();
    $("audit-panel").hidden = !isAdmin();

    if (!canManage()) {
      const active = document.querySelector(".nav-item.is-active");
      if (active && active.dataset.view === "documents") setView("dashboard");
      $("doc-table").innerHTML =
        '<tr><td colspan="9" class="table-empty">Sign in as a manager to manage documents.</td></tr>';
    }
  }

  async function loadSession() {
    try {
      const payload = await apiFetch("/api/auth/me");
      applySession(payload);
      if (canManage()) {
        loadDocumentMeta();
        loadDocuments();
      }
    } catch (_) {
      applySession(null);
    }
  }

  function openModal(name) {
    const modal = $(`${name}-modal`);
    if (modal) modal.hidden = false;
    if (name === "login") {
      $("login-error").hidden = true;
      setTimeout(() => $("login-username").focus(), 40);
    }
  }

  function closeModal(name) {
    const modal = $(`${name}-modal`);
    if (modal) modal.hidden = true;
  }

  async function submitLogin(event) {
    event.preventDefault();
    const username = $("login-username").value.trim();
    const password = $("login-password").value;
    const errorBox = $("login-error");
    const button = $("login-submit");

    errorBox.hidden = true;
    if (!username || !password) {
      errorBox.textContent = "Enter your username and password.";
      errorBox.hidden = false;
      return;
    }

    button.disabled = true;
    try {
      const payload = await apiFetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      applySession(payload);
      $("login-password").value = "";
      closeModal("login");
      toast(`Signed in as ${payload.user.username}`, "ok");
      if (canManage()) {
        setView("documents");
        loadDocumentMeta();
        loadDocuments();
      }
    } catch (error) {
      errorBox.textContent = error.message;
      errorBox.hidden = false;
    } finally {
      button.disabled = false;
    }
  }

  async function logout() {
    try {
      await apiFetch("/api/auth/logout", { method: "POST" });
    } catch (error) {
      /* ending a session that already expired is not an error for the user */
    }
    applySession(null);
    toast("Signed out", "ok");
    $("doc-table").innerHTML =
      '<tr><td colspan="9" class="table-empty">Sign in as a manager to manage documents.</td></tr>';
    if ($("audit-table")) {
      $("audit-table").innerHTML =
        '<tr><td colspan="6" class="table-empty">Administrators only.</td></tr>';
    }
  }

  /* ---------------- document management: data ---------------- */

  async function loadDocumentMeta() {
    if (!canManage() || management.meta) return;
    try {
      const meta = await apiFetch("/api/documents/meta");
      management.meta = meta;
      const category = $("f-category");
      category.innerHTML =
        '<option value="">Select a category</option>' +
        meta.categories.map((value) => `<option value="${esc(value)}">${esc(value)}</option>`).join("");
      $("department-options").innerHTML = meta.departments
        .map((value) => `<option value="${esc(value)}"></option>`)
        .join("");
      $("dropzone-hint").textContent = `PDF only · validated before storage · max ${meta.max_upload_size_mb} MB`;
    } catch (error) {
      toast(error.message, "error");
    }
  }

  async function loadDocuments() {
    if (!canManage()) return;
    const params = new URLSearchParams();
    if (management.statusFilter) params.set("status", management.statusFilter);
    if (management.search) params.set("q", management.search);

    try {
      const payload = await apiFetch(`/api/documents?${params.toString()}`);
      management.documents = payload.documents || [];
      management.stats = payload.stats || null;
      renderDocumentStats();
      renderDocumentTable();
    } catch (error) {
      $("doc-table").innerHTML = `<tr><td colspan="9" class="table-empty">${esc(
        error.message
      )}</td></tr>`;
    }
  }

  function renderDocumentStats() {
    const stats = management.stats || {};
    $("doc-kpi-total").textContent = stats.total ?? "0";
    $("doc-kpi-active").textContent = stats.active ?? "0";
    $("doc-kpi-pending").textContent = stats.pending_review ?? "0";
    $("doc-kpi-archived").textContent = stats.archived ?? "0";
    $("doc-kpi-failed").textContent = stats.failed ?? "0";
  }

  function statusPill(status, label) {
    const className = STATUS_PILL[status] || "status-archived";
    return `<span class="status-pill ${className}">${esc(label || status)}</span>`;
  }

  function formatDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return esc(value);
    return date.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" });
  }

  function documentActions(doc) {
    const key = esc(doc.document_key);
    const buttons = [
      `<button class="btn btn-xs" type="button" data-action="view" data-key="${key}">View</button>`,
    ];
    if (doc.status === "pending_review") {
      buttons.push(
        `<button class="btn btn-xs btn-primary" type="button" data-action="activate" data-key="${key}">Activate</button>`
      );
      buttons.push(
        `<button class="btn btn-xs btn-danger" type="button" data-action="reject" data-key="${key}">Reject</button>`
      );
    }
    if (doc.status === "active") {
      buttons.push(
        `<button class="btn btn-xs" type="button" data-action="archive" data-key="${key}">Archive</button>`
      );
    }
    if (doc.status === "failed") {
      buttons.push(
        `<button class="btn btn-xs btn-primary" type="button" data-action="retry" data-key="${key}">Retry</button>`
      );
    }
    if (doc.status !== "processing") {
      buttons.push(
        `<a class="btn btn-xs" href="/api/documents/${key}/file" target="_blank" rel="noopener">PDF</a>`
      );
    }
    return `<div class="row-actions">${buttons.join("")}</div>`;
  }

  function renderDocumentTable() {
    const body = $("doc-table");
    if (!management.documents.length) {
      body.innerHTML = `<tr><td colspan="9" class="table-empty">${
        management.search || management.statusFilter
          ? "No documents match this filter."
          : "No documents uploaded yet."
      }</td></tr>`;
      return;
    }
    body.innerHTML = management.documents
      .map(
        (doc) => `
        <tr>
          <td><span class="code-chip">${esc(doc.document_code)}</span></td>
          <td class="cell-strong">${esc(doc.document_title)}${doc.classification && doc.classification.related === false
            ? ' <span class="flag-warn" title="Automatic classification suggests this may not be a manufacturing document">check</span>'
            : ""}</td>
          <td>Rev ${esc(doc.revision)}</td>
          <td>${esc(doc.department || "—")}</td>
          <td>${formatDate(doc.effective_date)}</td>
          <td>${statusPill(doc.status, doc.status_label)}</td>
          <td>${formatDate(doc.uploaded_at)}</td>
          <td>${esc(doc.uploaded_by || "—")}</td>
          <td>${documentActions(doc)}</td>
        </tr>`
      )
      .join("");
  }

  /* ---------------- document management: actions ---------------- */

  async function runDocumentAction(action, key) {
    const doc = management.documents.find((item) => item.document_key === key);
    if (!doc) return;

    try {
      if (action === "view") {
        await showDocumentDetails(key);
        return;
      }

      if (action === "activate") {
        const text = `Activate ${doc.document_code} Rev ${doc.revision}?\n\nIt becomes searchable immediately and the revision it replaces is archived.`;
        if (!window.confirm(text)) return;
        const payload = await apiFetch(`/api/documents/${encodeURIComponent(key)}/activate`, { method: "POST" });
        toast(payload.message || "Revision activated", "ok");
      }

      if (action === "archive") {
        if (!window.confirm(`Archive ${doc.document_code} Rev ${doc.revision}? It will no longer be searchable.`)) return;
        const payload = await apiFetch(`/api/documents/${encodeURIComponent(key)}/archive`, { method: "POST" });
        toast(payload.message || "Revision archived", "ok");
      }

      if (action === "reject") {
        const reason = window.prompt(
          `Reject ${doc.document_code} Rev ${doc.revision}?\n\nOptional reason (shown in the audit trail):`,
          ""
        );
        if (reason === null) return;
        const payload = await apiFetch(`/api/documents/${encodeURIComponent(key)}/reject`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reason }),
        });
        toast(payload.message || "Revision rejected", "ok");
      }

      if (action === "retry") {
        const payload = await apiFetch(`/api/documents/${encodeURIComponent(key)}/retry`, { method: "POST" });
        toast(payload.message || "Reprocessing requested", payload.document.status === "failed" ? "error" : "ok");
      }

      await loadDocuments();
      loadStatus();
      if (isAdmin()) loadAudit();
    } catch (error) {
      toast(error.message, "error");
    }
  }

  async function showDocumentDetails(key) {
    try {
      const payload = await apiFetch(`/api/documents/${encodeURIComponent(key)}`);
      const doc = payload.document;
      const revisions = payload.revisions || [];

      $("detail-title").textContent = `${doc.document_code} Rev ${doc.revision}`;
      $("detail-subtitle").textContent = doc.document_title;

      const rows = [
        ["Status", statusPill(doc.status, doc.status_label)],
        ["Department", esc(doc.department || "—")],
        ["Category", esc(doc.category || "—")],
        ["Effective date", formatDate(doc.effective_date)],
        ["Pages / chunks", `${esc(doc.page_count ?? "—")} / ${esc(doc.chunk_count ?? "—")}`],
        ["Uploaded", `${formatDate(doc.uploaded_at)} by ${esc(doc.uploaded_by || "—")}`],
        ["Processed", formatDate(doc.processed_at)],
        ["Approved", doc.approved_at ? `${formatDate(doc.approved_at)} by ${esc(doc.approved_by || "—")}` : "—"],
        ["Archived", doc.archived_at ? `${formatDate(doc.archived_at)} by ${esc(doc.archived_by || "—")}` : "—"],
        ["Original file", esc(doc.source_filename || "—")],
        ["Description", esc(doc.description || "—")],
      ];

      const timeline = revisions.length
        ? revisions
            .map(
              (rev) => `
          <li class="timeline-item${rev.document_key === doc.document_key ? " is-current" : ""}">
            <span class="timeline-dot"></span>
            <div><strong>Rev ${esc(rev.revision)}</strong> ${statusPill(rev.status, rev.status_label)}
              <p>${esc(rev.uploaded_by || "—")} · ${formatDate(rev.uploaded_at)}</p></div>
          </li>`
            )
            .join("")
        : '<li class="timeline-item"><span class="timeline-dot"></span><div>No other revisions.</div></li>';

      const problems = [];
      if (doc.error) problems.push(`<p class="detail-error"><strong>Processing error:</strong> ${esc(doc.error)}</p>`);
      if (doc.rejection_reason) problems.push(`<p class="detail-error"><strong>Rejected:</strong> ${esc(doc.rejection_reason)}</p>`);
      (doc.warnings || []).forEach((warning) => problems.push(`<p class="detail-warning">${esc(warning)}</p>`));

      $("detail-body").innerHTML = `
        ${problems.join("")}
        <dl class="detail-grid">
          ${rows.map(([label, value]) => `<div><dt>${esc(label)}</dt><dd>${value}</dd></div>`).join("")}
        </dl>
        <h3 class="detail-heading">Revision history</h3>
        <ul class="timeline">${timeline}</ul>
        <div class="detail-actions">${documentActions(doc)}</div>`;

      openModal("detail");
    } catch (error) {
      toast(error.message, "error");
    }
  }

  /* ---------------- document management: upload ---------------- */

  function setSelectedFile(file) {
    management.file = file || null;
    const title = $("dropzone-title");
    const zone = $("dropzone");
    if (!file) {
      title.textContent = "Drop a PDF here, or click to browse";
      zone.classList.remove("has-file");
      return;
    }
    const sizeMb = (file.size / (1024 * 1024)).toFixed(2);
    title.textContent = `${file.name} · ${sizeMb} MB`;
    zone.classList.add("has-file");
  }

  function showUploadError(message) {
    const box = $("upload-error");
    if (!message) {
      box.hidden = true;
      box.textContent = "";
      return;
    }
    box.textContent = message;
    box.hidden = false;
  }

  function setUploadProgress(ratio, label) {
    const wrap = $("upload-progress");
    const bar = $("upload-progress-bar");
    if (ratio == null) {
      wrap.hidden = true;
      bar.style.width = "0%";
      return;
    }
    wrap.hidden = false;
    bar.style.width = `${Math.round(Math.max(0, Math.min(1, ratio)) * 100)}%`;
    bar.dataset.label = label || "";
  }

  function uploadWithProgress(formData) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/api/documents/upload");
      xhr.setRequestHeader("Accept", "application/json");
      if (management.csrf) xhr.setRequestHeader("X-CSRF-Token", management.csrf);
      xhr.upload.addEventListener("progress", (event) => {
        if (event.lengthComputable) setUploadProgress(event.loaded / event.total, "Uploading");
      });
      xhr.addEventListener("load", () => {
        let payload = null;
        try {
          payload = JSON.parse(xhr.responseText);
        } catch (_) {
          /* no JSON body */
        }
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(payload);
        } else {
          const message = payload && payload.detail
            ? formatDetail(payload.detail)
            : `Upload failed (${xhr.status}).`;
          const error = new Error(message);
          error.status = xhr.status;
          reject(error);
        }
      });
      xhr.addEventListener("error", () => reject(new Error("Could not reach the server during the upload.")));
      xhr.send(formData);
    });
  }

  async function submitUpload(event) {
    event.preventDefault();
    if (management.uploading) return;

    showUploadError("");
    const code = $("f-code").value.trim();
    const revision = $("f-revision").value.trim();
    const title = $("f-title").value.trim();
    const department = $("f-department").value.trim();
    const category = $("f-category").value;
    const effective = $("f-effective").value;
    const description = $("f-description").value.trim();

    if (!management.file) return showUploadError("Choose the PDF to upload.");
    if (!management.file.name.toLowerCase().endsWith(".pdf")) return showUploadError("Only PDF files can be uploaded.");
    if (!code || !revision || !title || !department || !category || !effective) {
      return showUploadError("Fill in every required field marked with *.");
    }

    const formData = new FormData();
    formData.append("file", management.file, management.file.name);
    formData.append("document_code", code);
    formData.append("document_title", title);
    formData.append("revision", revision);
    formData.append("department", department);
    formData.append("category", category);
    formData.append("effective_date", effective);
    formData.append("description", description);

    const button = $("upload-submit");
    button.disabled = true;
    management.uploading = true;
    setUploadProgress(0, "Uploading");

    try {
      const payload = await uploadWithProgress(formData);
      setUploadProgress(1, "Processing");
      const document = payload.document || {};
      if (document.status === "failed") {
        showUploadError(document.error || "Processing failed. See the register for details.");
        toast("Upload stored, but processing failed", "error");
      } else {
        toast(payload.message || "Upload processed and awaiting review", "ok");
      }
      $("upload-form").reset();
      setSelectedFile(null);
      await loadDocuments();
      loadStatus();
      if (document.document_key) await showDocumentDetails(document.document_key);
    } catch (error) {
      showUploadError(error.message);
      toast(error.message, "error");
    } finally {
      management.uploading = false;
      button.disabled = false;
      setTimeout(() => setUploadProgress(null), 900);
    }
  }

  /* ---------------- document management: audit ---------------- */

  async function loadAudit() {
    if (!isAdmin()) return;
    try {
      const payload = await apiFetch("/api/audit?limit=50");
      management.audit = payload.records || [];
      const body = $("audit-table");
      if (!management.audit.length) {
        body.innerHTML = '<tr><td colspan="6" class="table-empty">No audit records yet.</td></tr>';
        return;
      }
      body.innerHTML = management.audit
        .map(
          (record) => `
        <tr>
          <td>${formatDate(record.timestamp)}</td>
          <td class="cell-strong">${esc(record.username || "—")}</td>
          <td><span class="code-chip">${esc(record.action)}</span></td>
          <td>${esc(record.document_key || "—")}${record.revision ? ` <span class="muted">Rev ${esc(record.revision)}</span>` : ""}</td>
          <td>${record.result === "success" ? '<span class="status-pill status-active">ok</span>' : '<span class="status-pill status-failed">refused</span>'}</td>
          <td>${esc(record.detail || "—")}</td>
        </tr>`
        )
        .join("");
    } catch (error) {
      $("audit-table").innerHTML = `<tr><td colspan="6" class="table-empty">${esc(error.message)}</td></tr>`;
    }
  }

  /* ---------------- toasts ---------------- */

  function toast(message, variant = "ok") {
    const stack = $("toast-stack");
    if (!stack) return;
    const node = document.createElement("div");
    node.className = `toast toast-${variant}`;
    node.textContent = message;
    stack.appendChild(node);
    setTimeout(() => node.remove(), 6000);
  }

  /* ---------------- document management: wiring ---------------- */

  $("login-btn").addEventListener("click", () => openModal("login"));
  $("login-form").addEventListener("submit", submitLogin);
  $("logout-btn").addEventListener("click", logout);

  document.querySelectorAll("[data-close]").forEach((element) => {
    element.addEventListener("click", () => closeModal(element.dataset.close));
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeModal("login");
      closeModal("detail");
    }
  });

  $("toggle-upload").addEventListener("click", () => {
    const form = $("upload-form");
    form.hidden = !form.hidden;
    $("toggle-upload").textContent = form.hidden ? "Show form" : "Hide form";
    if (!form.hidden) $("f-code").focus();
  });

  const dropzone = $("dropzone");
  const fileInput = $("file-input");
  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      fileInput.click();
    }
  });
  ["dragenter", "dragover"].forEach((name) =>
    dropzone.addEventListener(name, (event) => {
      event.preventDefault();
      dropzone.classList.add("is-dragging");
    })
  );
  ["dragleave", "drop"].forEach((name) =>
    dropzone.addEventListener(name, (event) => {
      event.preventDefault();
      dropzone.classList.remove("is-dragging");
    })
  );
  dropzone.addEventListener("drop", (event) => {
    const file = event.dataTransfer && event.dataTransfer.files ? event.dataTransfer.files[0] : null;
    if (file) setSelectedFile(file);
  });
  fileInput.addEventListener("change", () => setSelectedFile(fileInput.files[0]));
  $("upload-form").addEventListener("submit", submitUpload);

  $("doc-search").addEventListener("input", (event) => {
    management.search = event.target.value.trim();
    clearTimeout(management.searchTimer);
    management.searchTimer = setTimeout(loadDocuments, 250);
  });

  $("doc-filters").addEventListener("click", (event) => {
    const button = event.target.closest("[data-status]");
    if (!button) return;
    management.statusFilter = button.dataset.status;
    $("doc-filters").querySelectorAll("button").forEach((item) => {
      item.classList.toggle("is-selected", item === button);
    });
    loadDocuments();
  });

  $("refresh-documents").addEventListener("click", loadDocuments);
  $("refresh-audit").addEventListener("click", loadAudit);

  $("doc-table").addEventListener("click", (event) => {
    const button = event.target.closest("[data-action]");
    if (!button) return;
    runDocumentAction(button.dataset.action, button.dataset.key);
  });

  $("detail-body").addEventListener("click", (event) => {
    const button = event.target.closest("[data-action]");
    if (!button) return;
    closeModal("detail");
    runDocumentAction(button.dataset.action, button.dataset.key);
  });

  /* ---------------- wiring ---------------- */

  document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", () => setView(button.dataset.view));
  });

  $("menu-btn").addEventListener("click", openDrawer);
  scrim.addEventListener("click", closeDrawer);
  $("refresh-dashboard").addEventListener("click", loadStatus);
  $("refresh-knowledge").addEventListener("click", loadStatus);

  buildChips($("dashboard-chips"), true);
  buildChips($("assistant-chips"), false);
  showEmptyState(true);
  loadStatus();
  loadSession();
  autosize();
})();
