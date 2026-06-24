"use strict";

// --- tiny DOM helper ------------------------------------------------------
function h(tag, props, ...children) {
  const node = document.createElement(tag);
  if (props) {
    for (const [k, v] of Object.entries(props)) {
      if (v === null || v === undefined) continue;
      if (k === "class") node.className = v;
      else if (k.startsWith("on") && typeof v === "function") {
        node.addEventListener(k.slice(2).toLowerCase(), v);
      } else node.setAttribute(k, v);
    }
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
function errbox(msg) { return h("div", { class: "errbox" }, msg); }
function pretty(value) { return JSON.stringify(value, null, 2); }

// --- API client -----------------------------------------------------------
// Static build: the `dip` engine runs entirely in the browser (see engine.js).
// DIP.handle mirrors the server's Api.handle, so this is a drop-in for fetch()
// — same routes, same JSON shapes, same error envelopes — and the rest of the
// UI below is byte-for-byte identical to the server-backed version.
async function api(method, path, body) {
  if (typeof DIP === "undefined" || !DIP.handle) {
    throw new Error("engine.js failed to load");
  }
  const resp = DIP.handle(method, path, body);
  if (resp.status >= 400) {
    throw new Error((resp.data && resp.data.error) || `HTTP ${resp.status}`);
  }
  return resp.data;
}

let modelsCache = [];

// --- health ---------------------------------------------------------------
async function loadHealth() {
  const badge = document.getElementById("health");
  try {
    const h0 = await api("GET", "/api/health");
    badge.textContent = `engine ok · ${h0.models} models · in-browser`;
    badge.className = "health ok";
  } catch (e) {
    badge.textContent = "engine unreachable";
    badge.className = "health down";
  }
}

// --- Models ---------------------------------------------------------------
async function loadModels() {
  const list = document.getElementById("models-list");
  clear(list);
  try {
    modelsCache = await api("GET", "/api/models");
  } catch (e) {
    list.append(errbox(e.message));
    return;
  }
  for (const m of modelsCache) {
    const card = h("div", { class: "card model-card" });
    card.append(
      h("div", { class: "model-head" },
        h("span", { class: "model-name" }, m.name),
        h("span", { class: "badge" }, `${m.rule_count} rule${m.rule_count === 1 ? "" : "s"}`)),
      h("div", { class: "model-meta" },
        h("span", null, `inputs: ${m.inputs.length ? m.inputs.join(", ") : "—"}`),
        h("span", null, `default: ${m.default_outcome}`)),
      h("button", { class: "link", onclick: () => toggleRules(m.name, card) }, "view rules"),
    );
    list.append(card);
  }
}

async function toggleRules(name, card) {
  const existing = card.querySelector(".rules");
  if (existing) { existing.remove(); return; }
  let model;
  try { model = await api("GET", "/api/models/" + encodeURIComponent(name)); }
  catch (e) { card.append(errbox(e.message)); return; }
  const box = h("div", { class: "rules" });
  for (const r of model.rules) {
    const conds = r.conditions.length
      ? r.conditions.map((c) => `${c.field} ${c.operator} ${JSON.stringify(c.value)}`).join(` ${r.logic.toUpperCase()} `)
      : "always";
    box.append(h("div", { class: "rule" },
      h("span", { class: "rule-name" }, `${r.name} → ${r.outcome}`),
      h("span", { class: "cond" }, `[p${r.priority}] ${conds}`)));
  }
  if (!model.rules.length) box.append(h("div", { class: "rule cond" }, "no rules — always returns the default outcome"));
  card.append(box);
}

const EXAMPLE_MODEL = {
  name: "kyc",
  inputs: ["country", "pep"],
  default_outcome: "review",
  rules: [
    { name: "block-sanctioned", priority: 30, conditions: [{ field: "country", operator: "in", value: ["XX", "YY"] }], outcome: "block" },
    { name: "clear-low-risk", priority: 10, logic: "all", conditions: [{ field: "pep", operator: "eq", value: false }], outcome: "clear" },
  ],
};

async function registerModel() {
  const msg = document.getElementById("model-msg");
  msg.textContent = "";
  msg.className = "msg";
  let body;
  try { body = JSON.parse(document.getElementById("model-json").value); }
  catch (e) { msg.textContent = "Invalid JSON: " + e.message; msg.className = "msg err"; return; }
  try {
    const saved = await api("POST", "/api/models", body);
    msg.textContent = `Registered "${saved.name}" (${saved.rules.length} rules).`;
    msg.className = "msg ok";
    await loadModels();
    await loadHealth();
  } catch (e) {
    msg.textContent = e.message;
    msg.className = "msg err";
  }
}

// --- Decide ---------------------------------------------------------------
function modelByName(name) { return modelsCache.find((m) => m.name === name); }

function prefillInputs(textarea, modelName) {
  const m = modelByName(modelName);
  const obj = {};
  if (m) for (const key of m.inputs) obj[key] = null;
  textarea.value = pretty(obj);
}

function refreshDecideModels() {
  const sel = document.getElementById("decide-model");
  const current = sel.value;
  clear(sel);
  for (const m of modelsCache) sel.append(h("option", { value: m.name }, m.name));
  if (current && modelByName(current)) sel.value = current;
  prefillInputs(document.getElementById("decide-inputs"), sel.value);
}

async function runDecide() {
  const out = document.getElementById("decide-result");
  clear(out);
  const model = document.getElementById("decide-model").value;
  let inputs;
  try { inputs = JSON.parse(document.getElementById("decide-inputs").value || "{}"); }
  catch (e) { out.append(errbox("Inputs must be valid JSON: " + e.message)); return; }
  try {
    const result = await api("POST", "/api/decide", { model, inputs });
    out.append(renderResult(result));
    await loadHealth();
  } catch (e) {
    out.append(errbox(e.message));
  }
}

function renderResult(r) {
  return h("div", { class: "result" },
    h("div", { class: "outcome" },
      h("span", { class: "outcome-label" }, "outcome"),
      h("span", { class: "outcome-value " + (r.matched ? "matched" : "default") }, String(r.outcome))),
    h("div", { class: "result-meta" },
      r.matched ? `matched rule: ${r.matched_rule}` : "no rule matched — used the model's default outcome"),
    h("div", { class: "trace" },
      h("div", { class: "trace-title" }, "decision trace (evaluated in priority order)"),
      ...r.trace.map((s) => h("div", { class: "trace-step " + (s.matched ? "hit" : "miss") },
        h("span", { class: "dot" }),
        h("span", null, s.rule),
        h("span", { class: "trace-flag" }, s.matched ? "matched ✓" : "skipped"))),
      r.trace.length === 0 ? h("div", { class: "empty" }, "no rules evaluated") : null));
}

// --- Orchestrate ----------------------------------------------------------
function modelOptions(selected) {
  const sel = h("select");
  for (const m of modelsCache) {
    const opt = h("option", { value: m.name }, m.name);
    if (m.name === selected) opt.setAttribute("selected", "selected");
    sel.append(opt);
  }
  return sel;
}

function addFlowStep(model, mapperText) {
  const steps = document.getElementById("flow-steps");
  const step = h("div", { class: "flow-step" });
  const num = steps.children.length + 1;
  step.append(
    h("div", { class: "flow-step-head" },
      h("span", { class: "step-num" }, `step ${num}`),
      modelOptions(model),
      h("button", { class: "remove link", onclick: () => { step.remove(); renumberSteps(); } }, "remove")),
    h("label", null, "mapper — one 'target = source' per line (optional)"),
    h("textarea", { rows: "2", spellcheck: "false" }, mapperText || ""),
  );
  steps.append(step);
}

function renumberSteps() {
  document.querySelectorAll("#flow-steps .flow-step .step-num").forEach((el, i) => {
    el.textContent = `step ${i + 1}`;
  });
}

function refreshFlowModels() {
  // Rebuild selects to reflect the current model list, preserving selection.
  document.querySelectorAll("#flow-steps .flow-step").forEach((step) => {
    const old = step.querySelector("select");
    const chosen = old.value;
    old.replaceWith(modelOptions(chosen));
  });
}

function parseMapper(text) {
  const mapper = {};
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const idx = trimmed.indexOf("=");
    if (idx === -1) continue;
    const target = trimmed.slice(0, idx).trim();
    const source = trimmed.slice(idx + 1).trim();
    if (target && source) mapper[target] = source;
  }
  return mapper;
}

async function runFlow() {
  const out = document.getElementById("flow-result");
  clear(out);
  const steps = [];
  for (const row of document.querySelectorAll("#flow-steps .flow-step")) {
    const service = row.querySelector("select").value;
    const mapper = parseMapper(row.querySelector("textarea").value);
    const step = { service };
    if (Object.keys(mapper).length) step.mapper = mapper;
    steps.push(step);
  }
  if (!steps.length) { out.append(errbox("Add at least one step to the flow.")); return; }
  let inputs;
  try { inputs = JSON.parse(document.getElementById("flow-inputs").value || "{}"); }
  catch (e) { out.append(errbox("Initial inputs must be valid JSON: " + e.message)); return; }
  try {
    const result = await api("POST", "/api/flows/run", { steps, inputs });
    out.append(renderFlowResult(result));
    await loadHealth();
  } catch (e) {
    out.append(errbox(e.message));
  }
}

function renderFlowResult(fr) {
  const wrap = h("div");
  for (const [name, r] of Object.entries(fr.results)) {
    wrap.append(h("div", { class: "flow-result-step" },
      h("div", null,
        h("span", { class: "step-model" }, name),
        h("span", null, " → "),
        h("span", { class: "step-outcome" }, String(r.outcome))),
      h("div", { class: "result-meta" },
        r.matched ? `matched rule: ${r.matched_rule}` : "default outcome")));
  }
  wrap.append(h("div", { class: "final-outcome" }, "final outcome: ", h("b", null, String(fr.final_outcome))));
  return wrap;
}

// --- Governance -----------------------------------------------------------
async function loadAudit() {
  const body = document.getElementById("audit-body");
  clear(body);
  const model = document.getElementById("audit-filter").value.trim();
  const path = model ? "/api/audit?model=" + encodeURIComponent(model) : "/api/audit";
  let entries;
  try { entries = await api("GET", path); }
  catch (e) { body.append(h("tr", null, h("td", { colspan: "5" }, errbox(e.message)))); return; }
  if (!entries.length) {
    body.append(h("tr", null, h("td", { class: "empty", colspan: "5" }, "no decisions recorded yet")));
    return;
  }
  for (const e of entries.slice().reverse()) {
    body.append(h("tr", null,
      h("td", null, h("code", null, e.timestamp.replace("T", " ").replace("+00:00", ""))),
      h("td", null, e.model),
      h("td", null, h("code", null, pretty(e.inputs).replace(/\n\s*/g, " "))),
      h("td", null, String(e.outcome)),
      h("td", null, e.matched_rule || "—")));
  }
}

// --- wiring ---------------------------------------------------------------
function setupTabs() {
  const tabs = document.querySelectorAll(".tab");
  const panels = document.querySelectorAll(".panel");
  tabs.forEach((tab) => tab.addEventListener("click", () => {
    tabs.forEach((t) => t.classList.toggle("active", t === tab));
    const target = tab.dataset.target;
    panels.forEach((p) => p.classList.toggle("active", p.id === target));
    if (target === "panel-decide") refreshDecideModels();
    if (target === "panel-orchestrate") refreshFlowModels();
    if (target === "panel-governance") loadAudit();
  }));
}

function loadExampleFlow() {
  clear(document.getElementById("flow-steps"));
  addFlowStep("risk", "");
  addFlowStep("routing", "risk = risk_outcome");
  document.getElementById("flow-inputs").value = pretty({ amount: 50000 });
}

document.addEventListener("DOMContentLoaded", async () => {
  setupTabs();
  document.getElementById("model-json").value = pretty(EXAMPLE_MODEL);
  document.getElementById("register-model").addEventListener("click", registerModel);
  document.getElementById("run-decide").addEventListener("click", runDecide);
  document.getElementById("decide-model").addEventListener("change", (e) =>
    prefillInputs(document.getElementById("decide-inputs"), e.target.value));
  document.getElementById("add-step").addEventListener("click", () => addFlowStep());
  document.getElementById("load-example").addEventListener("click", loadExampleFlow);
  document.getElementById("run-flow").addEventListener("click", runFlow);
  document.getElementById("refresh-audit").addEventListener("click", loadAudit);

  await loadHealth();
  await loadModels();
  refreshDecideModels();
  loadExampleFlow();
});
