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
    about: {
      title: "System information",
      subtitle: "Runtime configuration, API surface and known limitations.",
    },
  };

  const state = { status: null, busy: false };

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

    $("sidebar-version").textContent = `v${status.version || "1.0.0"} · stage 6`;

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
  autosize();
})();
