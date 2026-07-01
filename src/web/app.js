"use strict";

/* ==========================================================================
   GUI Demo — MLLM-Assisted Concert Programme Metadata Extraction (DLfM 2026)
   app.js — all frontend behaviour, no build step, no framework.

   Note: there is deliberately no UI control for "number of repeated
   samples per image" here. The backend supports it (see annotate.py /
   schema_adapters.majority_pick_with_shares), but exposing it would add a
   cost/time-multiplier knob to what is meant to be a one-button "drop
   images, press play" flow. It defaults to a single pass per image.
   ========================================================================== */

const HELP_TEXT = {
  gemini: {
    label: "Google Gemini (free tier)",
    steps:
      "1. Open aistudio.google.com/apikey and sign in with a Google account.\n" +
      "2. Accept the terms — a default project is created automatically.\n" +
      "3. Click \"Create API key\" and copy it (shown once).\n" +
      "4. Paste it into the field above, or set GEMINI_API_KEY before launching.",
    url: "https://aistudio.google.com/apikey",
  },
};

/* ---------------------------------------------------------------------- */
/* App state                                                              */
/* ---------------------------------------------------------------------- */

const state = {
  config: null,
  schema: null, // parsed canonical schema, for the dynamic catalogue renderer
  schemaDefs: {},
  runId: null,
  pollTimer: null,
  results: { run_metadata: null, records: [] },
  currentIndex: 0,
  currentView: "original",
  selectedStems: new Set(), // stems clicked in the gallery
  inputDir: "",             // server-resolved absolute path to the input folder
};

/* ---------------------------------------------------------------------- */
/* Tiny API helper                                                        */
/* ---------------------------------------------------------------------- */

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  let body = null;
  try {
    body = await res.json();
  } catch (_err) {
    body = null;
  }
  if (!res.ok) {
    const message = (body && (body.detail || body.problems?.join("; "))) || res.statusText;
    const err = new Error(message);
    err.status = res.status;
    err.body = body;
    throw err;
  }
  return body;
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

/* ---------------------------------------------------------------------- */
/* Screen navigation                                                      */
/* ---------------------------------------------------------------------- */

function showScreen(name) {
  document.body.dataset.screen = name;
  for (const section of document.querySelectorAll(".screen")) {
    section.classList.toggle("is-active", section.id === `screen-${name}`);
  }
  for (const li of document.querySelectorAll(".stepper li")) {
    const step = li.dataset.step;
    li.classList.toggle("is-active", step === name);
    li.classList.toggle(
      "is-done",
      (name === "progress" && step === "setup") ||
        (name === "results" && (step === "setup" || step === "progress"))
    );
  }
}

/* ========================================================================
   SETUP SCREEN
   ======================================================================== */

function currentProvider() {
  return "gemini";
}

function populateModelSelect() {
  const select = document.getElementById("model-select");
  const provider = currentProvider();
  const models = state.config.models[provider] || [];
  select.innerHTML = models
    .map((m) => `<option value="${escapeHtml(m.id)}">${escapeHtml(m.label)}</option>`)
    .join("");
}

function updateApiKeyHint() {
  const hasEnvKey = state.config.env_key_present["gemini"];
  const hint = document.getElementById("api-key-hint");
  hint.innerHTML = hasEnvKey
    ? `Using <code>GEMINI_API_KEY</code> from your environment — leave this blank, or paste a key to override it for this run.`
    : `Stays in memory for this session only; never written to disk.`;
}

function updateGeminiUsageField() {
  const field = document.getElementById("gemini-usage-field");
  const u = state.config.gemini_usage;
  field.textContent =
    `Free-tier guard (local, conservative — not an official Google limit): ` +
    `${u.used_today} / ${u.daily_cap} requests used today, ~${u.min_interval_seconds}s between requests.`;
}

function onProviderChange() {
  populateModelSelect();
  updateApiKeyHint();
  updateGeminiUsageField();
}

function setupHelpLinks() {
  for (const link of document.querySelectorAll("a[data-help]")) {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      const info = HELP_TEXT[link.dataset.help];
      const existing = link.parentElement.querySelector(".help-steps");
      if (existing) {
        existing.remove();
        return;
      }
      const box = document.createElement("p");
      box.className = "field__hint help-steps";
      box.style.whiteSpace = "pre-line";
      box.innerHTML =
        escapeHtml(info.steps) + `\n<a href="${info.url}" target="_blank" rel="noopener">${info.url} →</a>`;
      link.parentElement.appendChild(box);
    });
  }
}

function updateSelectionUI() {
  const n = state.selectedStems.size;
  const selEl = document.getElementById("selected-count");
  const clearBtn = document.getElementById("clear-selection");
  selEl.hidden = n === 0;
  clearBtn.hidden = n === 0;
  selEl.textContent = n === 0 ? "" : `${n} selected`;
}

async function loadThumbnails() {
  const grid = document.getElementById("thumb-grid");
  const countEl = document.getElementById("image-count");
  grid.innerHTML = "";
  countEl.textContent = "loading…";
  try {
    const data = await api("/api/images");
    state.inputDir = data.dir;
    countEl.textContent = `${data.count} image${data.count === 1 ? "" : "s"}`;
    if (data.count === 0) {
      grid.innerHTML = '<p class="gallery-empty">No images found in the input folder.</p>';
      return;
    }
    const frag = document.createDocumentFragment();
    data.images.forEach((img, i) => {
      const cell = document.createElement("div");
      cell.className = "thumb";
      cell.dataset.stem = img.stem;
      cell.style.animationDelay = `${Math.min(i, 40) * 12}ms`;
      if (state.selectedStems.has(img.stem)) cell.classList.add("is-selected");
      cell.title = img.filename;
      cell.setAttribute("role", "button");
      cell.setAttribute("aria-pressed", state.selectedStems.has(img.stem) ? "true" : "false");
      cell.addEventListener("click", () => {
        if (state.selectedStems.has(img.stem)) {
          state.selectedStems.delete(img.stem);
          cell.classList.remove("is-selected");
          cell.setAttribute("aria-pressed", "false");
        } else {
          state.selectedStems.add(img.stem);
          cell.classList.add("is-selected");
          cell.setAttribute("aria-pressed", "true");
        }
        updateSelectionUI();
      });
      const el = document.createElement("img");
      el.loading = "lazy";
      el.src = `/api/image?dir=${encodeURIComponent(data.dir)}&stem=${encodeURIComponent(img.stem)}&view=original`;
      el.alt = img.filename;
      cell.appendChild(el);
      frag.appendChild(cell);
    });
    grid.appendChild(frag);
    updateSelectionUI();
  } catch (err) {
    countEl.textContent = "";
    grid.innerHTML = `<p class="gallery-empty">${escapeHtml(err.message)}</p>`;
  }
}

async function loadPromptAndSchema() {
  const promptData = await api("/api/prompt");
  document.getElementById("prompt-editor").value = promptData.text;

  const schemaData = await api("/api/schema");
  document.getElementById("schema-editor").value = schemaData.text;
  applySchemaText(schemaData.text);
}

function applySchemaText(text) {
  try {
    const parsed = JSON.parse(text);
    state.schema = parsed;
    state.schemaDefs = parsed.$defs || {};
    return true;
  } catch (_err) {
    return false;
  }
}

async function savePrompt() {
  const status = document.getElementById("prompt-save-status");
  status.textContent = "Saving…";
  status.className = "save-status";
  try {
    await api("/api/prompt", { method: "POST", body: JSON.stringify({ text: document.getElementById("prompt-editor").value }) });
    status.textContent = "Saved.";
    status.classList.add("is-ok");
  } catch (err) {
    status.textContent = err.message;
    status.classList.add("is-error");
  }
}

async function saveSchema() {
  const status = document.getElementById("schema-save-status");
  const text = document.getElementById("schema-editor").value;
  status.textContent = "Validating…";
  status.className = "save-status";
  try {
    await api("/api/schema", { method: "POST", body: JSON.stringify({ text }) });
    applySchemaText(text);
    status.textContent = "Saved.";
    status.classList.add("is-ok");
  } catch (err) {
    status.textContent = err.message;
    status.classList.add("is-error");
  }
}

function onOfflineModeToggle() {
  const offline = document.getElementById("offline-mode").checked;
  document.getElementById("api-key").disabled = offline;
  document.getElementById("model-select").disabled = offline;
  document.getElementById("run-button").textContent = offline
    ? "Run offline demo"
    : "Run annotation";
  // In offline mode the bundled 100 samples are the only valid source;
  // keep the gallery and count controls visible but note they still work.
}

function showRunError(message) {
  const el = document.getElementById("run-error");
  if (!message) {
    el.hidden = true;
    el.textContent = "";
    return;
  }
  el.hidden = false;
  el.textContent = message;
}

function showLiveRunConfirm() {
  return new Promise((resolve) => {
    const backdrop = document.getElementById("liverun-backdrop");
    const checkbox = document.getElementById("liverun-checkbox");
    const acceptBtn = document.getElementById("liverun-accept");
    const cancelBtn = document.getElementById("liverun-cancel");

    checkbox.checked = false;
    acceptBtn.disabled = true;
    backdrop.hidden = false;

    function cleanup(result) {
      backdrop.hidden = true;
      checkbox.removeEventListener("change", onCheck);
      acceptBtn.removeEventListener("click", onAccept);
      cancelBtn.removeEventListener("click", onCancel);
      resolve(result);
    }
    function onCheck() { acceptBtn.disabled = !checkbox.checked; }
    function onAccept() { cleanup(true); }
    function onCancel() { cleanup(false); }

    checkbox.addEventListener("change", onCheck);
    acceptBtn.addEventListener("click", onAccept);
    cancelBtn.addEventListener("click", onCancel);
  });
}

async function startRun() {
  showRunError("");
  const offline = document.getElementById("offline-mode").checked;

  if (!offline) {
    const confirmed = await showLiveRunConfirm();
    if (!confirmed) return;
  }
  const provider = offline ? "mock" : currentProvider();
  const selectedStems = [...state.selectedStems];
  const body = {
    provider,
    api_key: offline ? null : document.getElementById("api-key").value || null,
    model: offline ? "mock" : document.getElementById("model-select").value,
    send_binarised: document.getElementById("send-binarised").checked,
    // If images are selected in the gallery, use them; otherwise fall back to first N
    ...(selectedStems.length
      ? { image_stems: selectedStems }
      : { max_images: parseInt(document.getElementById("max-images").value, 10) || null }
    ),
  };

  const runButton = document.getElementById("run-button");
  runButton.disabled = true;
  try {
    const { run_id } = await api("/api/run", { method: "POST", body: JSON.stringify(body) });
    state.runId = run_id;
    showScreen("progress");
    resetProgressScreen();
    pollProgress();
  } catch (err) {
    showRunError(err.message);
  } finally {
    runButton.disabled = false;
  }
}

/* ========================================================================
   PROGRESS SCREEN
   ======================================================================== */

function resetProgressScreen() {
  document.getElementById("progress-fill").style.width = "0%";
  document.getElementById("progress-bar").setAttribute("aria-valuenow", "0");
  document.getElementById("progress-count-text").textContent = "0 / 0";
  document.getElementById("progress-current").textContent = "Starting…";
  document.getElementById("progress-list").innerHTML = "";
  document.getElementById("stop-button").disabled = false;
}

const STATUS_LABEL = {
  pending: "Waiting",
  running: "Annotating…",
  done: "Done",
  error: "Error",
  skipped: "Skipped",
};

function renderProgressList(images) {
  const list = document.getElementById("progress-list");
  list.innerHTML = "";
  const frag = document.createDocumentFragment();
  for (const img of images) {
    const li = document.createElement("li");
    li.dataset.state = img.state;
    const dot = document.createElement("span");
    dot.className = "status-dot";
    const label = document.createElement("span");
    label.textContent = `${img.filename} — ${STATUS_LABEL[img.state] || img.state}`;
    li.append(dot, label);
    if (img.error) {
      const errEl = document.createElement("span");
      errEl.className = "image-error";
      errEl.textContent = img.error;
      li.appendChild(errEl);
    }
    frag.appendChild(li);
  }
  list.appendChild(frag);
}

async function pollProgress() {
  clearTimeout(state.pollTimer);
  try {
    const progress = await api(`/api/progress/${state.runId}`);
    const pct = progress.total ? Math.round((progress.completed / progress.total) * 100) : 0;
    document.getElementById("progress-fill").style.width = `${pct}%`;
    document.getElementById("progress-bar").setAttribute("aria-valuenow", String(pct));
    document.getElementById("progress-count-text").textContent = `${progress.completed} / ${progress.total}`;
    renderProgressList(progress.images || []);

    const running = (progress.images || []).find((i) => i.state === "running");
    document.getElementById("progress-current").textContent = running
      ? `Annotating ${running.filename}…`
      : progress.finished_at
        ? "Finished."
        : "Starting…";

    if (progress.error) {
      document.getElementById("progress-current").textContent = `Could not start: ${progress.error}`;
    }

    if (progress.finished_at) {
      document.getElementById("stop-button").disabled = true;
      await loadResults();
      showScreen("results");
      return;
    }
  } catch (err) {
    document.getElementById("progress-current").textContent = `Error checking progress: ${err.message}`;
  }
  state.pollTimer = setTimeout(pollProgress, 600);
}

async function stopRun() {
  if (!state.runId) return;
  document.getElementById("stop-button").disabled = true;
  try {
    await api(`/api/cancel/${state.runId}`, { method: "POST" });
  } catch (_err) {
    /* the run may have already finished -- nothing to do */
  }
}

/* ========================================================================
   RESULTS SCREEN
   ======================================================================== */

async function loadResults() {
  const data = await api(`/api/results/${state.runId}`);
  state.results = data;
  state.currentIndex = 0;
  renderResultsRail();
  renderCurrentRecord();
  wireDownloadLinks();
}

function renderResultsRail() {
  const rail = document.getElementById("results-rail");
  rail.innerHTML = "";
  const inputDir = state.results.run_metadata.input_dir;
  const frag = document.createDocumentFragment();
  state.results.records.forEach((rec, i) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = i === 0 ? "is-active" : "";
    btn.dataset.index = String(i);
    const img = document.createElement("img");
    img.loading = "lazy";
    img.src = `/api/image?dir=${encodeURIComponent(inputDir)}&stem=${encodeURIComponent(rec.stem)}&view=original`;
    img.alt = rec.stem;
    btn.appendChild(img);
    btn.addEventListener("click", () => {
      state.currentIndex = i;
      renderCurrentRecord();
    });
    frag.appendChild(btn);
  });
  rail.appendChild(frag);
}

function setActiveRailButton() {
  for (const btn of document.querySelectorAll(".results-rail button")) {
    btn.classList.toggle("is-active", Number(btn.dataset.index) === state.currentIndex);
  }
}

function renderCurrentRecord() {
  const records = state.results.records;
  if (!records.length) {
    document.getElementById("catalogue-pane").innerHTML = '<p class="empty-state">No annotations in this run.</p>';
    return;
  }
  setActiveRailButton();
  const rec = records[state.currentIndex];
  document.getElementById("record-position").textContent = `${state.currentIndex + 1} / ${records.length}`;

  updateRecordImage();
  renderCataloguePane(rec.record);
  document.getElementById("catalogue-pane").scrollTop = 0;
}

function updateRecordImage() {
  const rec = state.results.records[state.currentIndex];
  const inputDir = state.results.run_metadata.input_dir;
  const img = document.getElementById("record-image");
  img.src = `/api/image?dir=${encodeURIComponent(inputDir)}&stem=${encodeURIComponent(rec.stem)}&view=${state.currentView}`;
  img.alt = `${state.currentView === "binarised" ? "Binarised" : "Original"} scan of ${rec.stem}`;
}

function setView(view) {
  state.currentView = view;
  for (const btn of document.querySelectorAll(".seg-control__option")) {
    btn.classList.toggle("is-active", btn.dataset.view === view);
  }
  updateRecordImage();
}

function navigate(delta) {
  const total = state.results.records.length;
  if (!total) return;
  state.currentIndex = (state.currentIndex + delta + total) % total;
  renderCurrentRecord();
}

function wireDownloadLinks() {
  document.getElementById("download-csv").href = `/api/results/${state.runId}/download/csv`;
  document.getElementById("download-jsonl").href = `/api/results/${state.runId}/download/jsonl`;
}

/* ---- Dynamic, schema-driven catalogue rendering ------------------------ */

function resolveRef(node) {
  if (node && node.$ref) {
    const name = node.$ref.split("/").pop();
    return state.schemaDefs[name] || {};
  }
  return node || {};
}

/** {"anyOf": [<T>, {"type": "null"}]} -> {inner: <T>, nullable: true} */
function splitNullable(node) {
  if (Array.isArray(node.anyOf) && node.anyOf.length === 2) {
    const nullBranch = node.anyOf.find((b) => b.type === "null");
    const other = node.anyOf.find((b) => b.type !== "null");
    if (nullBranch && other) {
      const inner = resolveRef(other);
      return {
        inner: { ...inner, title: node.title || inner.title, description: node.description || inner.description },
        nullable: true,
      };
    }
  }
  return { inner: resolveRef(node), nullable: false };
}

function formatPerformer(p) {
  if (!p) return "";
  const roles = Array.isArray(p.roles) ? p.roles.filter(Boolean).join(", ") : p.roles || "";
  return roles ? `${p.name || "?"} (${roles})` : p.name || "?";
}

function renderCataloguePane(record) {
  const pane = document.getElementById("catalogue-pane");
  pane.innerHTML = "";

  if (!state.schema) {
    pane.innerHTML = '<p class="empty-state">Schema unavailable.</p>';
    return;
  }

  const rootProps = state.schema.properties || {};
  const concertsSchema = splitNullable(rootProps.concerts || {}).inner;
  const concertItemSchema = resolveRef(concertsSchema.items || {});
  const concerts = Array.isArray(record?.concerts) ? record.concerts : [];

  if (!concerts.length) {
    pane.innerHTML = '<p class="empty-state">No concerts were extracted from this image.</p>';
    return;
  }

  const frag = document.createDocumentFragment();
  concerts.forEach((concert, idx) => {
    frag.appendChild(renderConcertCard(concertItemSchema, concert, idx, concerts.length));
  });
  pane.appendChild(frag);
}

function renderConcertCard(concertSchema, concertValue, index, total) {
  const card = document.createElement("article");
  card.className = "catalogue-card";

  const heading = document.createElement("h3");
  heading.className = "catalogue-card__title";
  const titleText = concertValue.c_title || concertValue.c_series_no;
  heading.textContent = total > 1
    ? `Concert ${index + 1}${titleText ? ` — ${titleText}` : ""}`
    : (titleText || "Concert");
  card.appendChild(heading);

  const rule = document.createElement("hr");
  rule.className = "catalogue-card__rule";
  card.appendChild(rule);

  const properties = concertSchema.properties || {};
  const dl = document.createElement("dl");
  dl.className = "record-fields";
  for (const [key, rawPropSchema] of Object.entries(properties)) {
    if (key === "works") continue;
    appendFieldRow(dl, key, rawPropSchema, concertValue?.[key]);
  }
  card.appendChild(dl);

  const works = Array.isArray(concertValue.works) ? concertValue.works : [];
  if (works.length) {
    const worksHeading = document.createElement("p");
    worksHeading.className = "works-heading";
    worksHeading.textContent = `Works (${works.length})`;
    card.appendChild(worksHeading);

    const worksSchema = resolveRef(splitNullable(properties.works || {}).inner.items || properties.works?.items || {});
    works.forEach((work, i) => card.appendChild(renderWorkBlock(worksSchema, work, i)));
  }

  return card;
}

function appendFieldRow(dl, key, rawPropSchema, value) {
  const { inner } = splitNullable(rawPropSchema);
  const dt = document.createElement("dt");
  dt.textContent = inner.title || key;
  if (inner.description) dt.title = inner.description;
  const dd = document.createElement("dd");

  if (inner.type === "array") {
    const items = Array.isArray(value) ? value.filter((v) => v !== null && v !== undefined) : [];
    if (!items.length) {
      dd.textContent = "—";
      dd.classList.add("is-empty");
    } else {
      const itemSchema = resolveRef(inner.items || {});
      const isObjectList = itemSchema.type === "object";
      if (isObjectList) {
        // Performer objects: one line each
        const ul = document.createElement("ul");
        ul.className = "field-list";
        items.forEach((p) => {
          const li = document.createElement("li");
          li.textContent = formatPerformer(p);
          ul.appendChild(li);
        });
        dd.appendChild(ul);
      } else if (items.length === 1) {
        dd.textContent = items[0];
      } else {
        // String arrays (e.g. c_comp_list, roles): one bullet per entry
        const ul = document.createElement("ul");
        ul.className = "field-list";
        items.forEach((s) => {
          const li = document.createElement("li");
          li.textContent = s;
          ul.appendChild(li);
        });
        dd.appendChild(ul);
      }
    }
  } else {
    const text = value === null || value === undefined || value === "" ? null : String(value);
    dd.textContent = text ?? "—";
    if (text === null) dd.classList.add("is-empty");
  }
  dl.append(dt, dd);
}

function renderWorkBlock(workSchema, workValue, index) {
  const block = document.createElement("div");
  block.className = "work-block";

  const heading = document.createElement("p");
  heading.className = "work-block__heading";
  const title = workValue.w_title || "(untitled work)";
  const comp = workValue.w_comp;
  heading.innerHTML =
    `<span class="work-number">${index + 1}.</span> <span class="work-title">${escapeHtml(title)}</span>` +
    (comp ? ` <span class="work-composer">— ${escapeHtml(comp)}</span>` : "");
  block.appendChild(heading);

  const properties = workSchema.properties || {};
  const skip = new Set(["w_position", "w_title", "w_comp", "w_movements", "w_perf_list"]);
  const extraKeys = Object.keys(properties).filter((k) => !skip.has(k));
  if (extraKeys.length) {
    const dl = document.createElement("dl");
    dl.className = "work-extra-fields";
    for (const key of extraKeys) appendFieldRow(dl, key, properties[key], workValue?.[key]);
    block.appendChild(dl);
  }

  const movements = Array.isArray(workValue.w_movements) ? workValue.w_movements.filter(Boolean) : [];
  if (movements.length) {
    const ol = document.createElement("ol");
    ol.className = "movement-list";
    for (const m of movements) {
      const li = document.createElement("li");
      li.textContent = m?.m_title || "(untitled movement)";
      ol.appendChild(li);
    }
    block.appendChild(ol);
  }

  const performers = Array.isArray(workValue.w_perf_list) ? workValue.w_perf_list.filter(Boolean) : [];
  if (performers.length) {
    const p = document.createElement("p");
    p.className = "performer-line";
    p.textContent = "Performers: " + performers.map(formatPerformer).join("; ");
    block.appendChild(p);
  }

  return block;
}

/* ========================================================================
   Previous runs picker
   ======================================================================== */

function formatRunLabel(run) {
  const dt = run.started_at ? new Date(run.started_at) : null;
  const dateStr = dt
    ? dt.toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" })
    : run.run_id;
  const providerLabel = run.provider === "mock" ? "offline demo" : `${run.provider} / ${run.model}`;
  const imageCount = `${run.completed_images ?? "?"}/${run.total_images ?? "?"} images`;
  const status = run.cancelled ? " — stopped" : run.errors > 0 ? ` — ${run.errors} error(s)` : "";
  return `${dateStr} · ${imageCount} · ${providerLabel}${status}`;
}

async function loadPreviousRuns() {
  try {
    const data = await api("/api/runs");
    const runs = (data.runs || []).filter((r) => r.finished_at);
    const container = document.getElementById("prev-runs");
    const list = document.getElementById("prev-runs-list");
    list.innerHTML = "";
    if (!runs.length) {
      container.hidden = true;
      return;
    }
    runs.forEach((run) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn btn--ghost prev-run-item";
      btn.textContent = formatRunLabel(run);
      btn.addEventListener("click", () => openPreviousRun(run.run_id));
      list.appendChild(btn);
    });
    container.hidden = false;
  } catch {
    // silently ignore — not critical
  }
}

async function openPreviousRun(runId) {
  state.runId = runId;
  showScreen("results");
  await loadResults();
}

/* ========================================================================
   Wiring
   ======================================================================== */

/* ========================================================================
   Consent gate (clickwrap — stored in localStorage, re-prompts on version bump)
   ======================================================================== */

const CONSENT_VERSION = "1";
const CONSENT_KEY = `cpa-consent-v${CONSENT_VERSION}`;

function consentAlreadyGiven() {
  try { return !!localStorage.getItem(CONSENT_KEY); } catch { return false; }
}

function recordConsent() {
  try {
    localStorage.setItem(CONSENT_KEY, JSON.stringify({
      version: CONSENT_VERSION,
      acceptedAt: new Date().toISOString(),
    }));
  } catch { /* localStorage unavailable — don't block use */ }
}

function setupConsentGate() {
  if (consentAlreadyGiven()) return; // already accepted in a previous session

  const backdrop = document.getElementById("consent-backdrop");
  const checkbox = document.getElementById("consent-checkbox");
  const acceptBtn = document.getElementById("consent-accept");

  backdrop.hidden = false;
  // Trap focus in the card
  backdrop.focus?.();

  checkbox.addEventListener("change", () => {
    acceptBtn.disabled = !checkbox.checked;
  });

  acceptBtn.addEventListener("click", () => {
    if (!checkbox.checked) return;
    recordConsent();
    backdrop.hidden = true;
  });
}

/* ========================================================================
   Wiring
   ======================================================================== */

async function init() {
  setupConsentGate();
  setupHelpLinks();

  state.config = await api("/api/config");
  populateModelSelect();
  updateApiKeyHint();
  updateGeminiUsageField();

  document.getElementById("offline-mode").addEventListener("change", onOfflineModeToggle);
  document.getElementById("run-button").addEventListener("click", startRun);
  document.getElementById("save-prompt").addEventListener("click", savePrompt);
  document.getElementById("save-schema").addEventListener("click", saveSchema);
  document.getElementById("stop-button").addEventListener("click", stopRun);
  document.getElementById("clear-selection").addEventListener("click", () => {
    state.selectedStems.clear();
    for (const cell of document.querySelectorAll(".thumb.is-selected")) {
      cell.classList.remove("is-selected");
      cell.setAttribute("aria-pressed", "false");
    }
    updateSelectionUI();
  });
  document.getElementById("back-to-setup").addEventListener("click", () => {
    showScreen("setup");
    loadPreviousRuns();
  });

  document.getElementById("prev-image").addEventListener("click", () => navigate(-1));
  document.getElementById("next-image").addEventListener("click", () => navigate(1));
  for (const btn of document.querySelectorAll(".seg-control__option")) {
    btn.addEventListener("click", () => setView(btn.dataset.view));
  }
  document.addEventListener("keydown", (event) => {
    if (!document.getElementById("screen-results").classList.contains("is-active")) return;
    if (event.target.tagName === "INPUT" || event.target.tagName === "TEXTAREA") return;
    if (event.key === "ArrowLeft") navigate(-1);
    if (event.key === "ArrowRight") navigate(1);
  });

  await Promise.all([loadThumbnails(), loadPromptAndSchema(), loadPreviousRuns()]);
}

init().catch((err) => {
  console.error(err);
  showRunError(`Could not initialise the app: ${err.message}`);
});
