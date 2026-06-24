"use strict";
/*
 * In-browser port of the `dip` decision engine + the app's JSON API.
 *
 * This is a faithful reimplementation of the Python packages (dip/ + app/) so
 * the Decision Intelligence Console can run as a fully static site (e.g. GitHub
 * Pages) with NO backend. `DIP.handle(method, path, body)` mirrors
 * `app.api.Api.handle` exactly — same routes, same JSON shapes, same errors —
 * so the UI in app.js is unchanged except for swapping fetch() for this.
 *
 * Parity with the Python engine is checked by tools/verify-engine.mjs.
 */
(function () {
  // --- errors (mirror dip/errors.py + app/errors.py) ----------------------
  class DIPError extends Error {}
  class ConditionError extends DIPError {}
  class ValidationError extends DIPError {}
  class CompositionError extends DIPError {}

  class AppError extends Error {
    constructor(status, msg) { super(msg); this.status = status; }
  }
  class BadRequest extends AppError { constructor(m) { super(400, m); } }
  class NotFound extends AppError { constructor(m) { super(404, m); } }
  class MethodNotAllowed extends AppError { constructor(m) { super(405, m); } }

  // --- operators (mirror dip/model.py Operator + _COMPARATORS) ------------
  // Insertion order matters: it drives the "expected one of: ..." message.
  const OPERATORS = ["eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in", "contains"];
  const OP_SET = new Set(OPERATORS);

  const repr = (v) => JSON.stringify(v);
  // Python-ish repr for the missing-inputs message: single-quoted strings.
  const pyRepr = (v) => (typeof v === "string" ? `'${v}'` : repr(v));

  function pyEq(a, b) {
    if (Array.isArray(a) && Array.isArray(b)) {
      return a.length === b.length && a.every((x, i) => pyEq(x, b[i]));
    }
    return a === b;
  }

  function ordCompatible(a, b) {
    if (typeof a === "number" && typeof b === "number") return true;
    if (typeof a === "string" && typeof b === "string") return true;
    return false;
  }

  function member(x, container) {
    if (Array.isArray(container)) return container.some((e) => pyEq(e, x));
    if (typeof container === "string") {
      if (typeof x !== "string") {
        throw new ConditionError(`cannot apply 'in'/'contains' to ${repr(x)} and ${repr(container)}`);
      }
      return container.includes(x);
    }
    if (container && typeof container === "object") {
      return Object.prototype.hasOwnProperty.call(container, x);
    }
    throw new ConditionError(`argument of type '${typeof container}' is not iterable`);
  }

  function applyOp(op, a, b) {
    switch (op) {
      case "eq": return pyEq(a, b);
      case "ne": return !pyEq(a, b);
      case "gt": case "gte": case "lt": case "lte":
        if (!ordCompatible(a, b)) {
          throw new ConditionError(`cannot apply ${repr(op)} to ${repr(a)} and ${repr(b)}`);
        }
        return op === "gt" ? a > b : op === "gte" ? a >= b : op === "lt" ? a < b : a <= b;
      case "in": return member(a, b);
      case "not_in": return !member(a, b);
      case "contains": return member(b, a);
      default: throw new ConditionError(`unknown operator ${repr(op)}`);
    }
  }

  // --- model evaluation (mirror dip/model.py + dip/engine.py) -------------
  function evaluateCondition(c, data) {
    if (!Object.prototype.hasOwnProperty.call(data, c.field)) {
      throw new ConditionError(`missing input field ${pyRepr(c.field)}`);
    }
    return applyOp(c.operator, data[c.field], c.value);
  }

  function ruleMatches(rule, data) {
    // Evaluate ALL conditions first (mirrors Python's list comprehension),
    // so a missing field still raises even if an earlier condition is false.
    const results = rule.conditions.map((c) => evaluateCondition(c, data));
    return rule.logic === "any" ? results.some(Boolean) : results.every(Boolean);
  }

  function orderedRules(model) {
    // Stable sort by descending priority (index tiebreaker preserves order).
    return model.rules
      .map((r, i) => [r, i])
      .sort((a, b) => b[0].priority - a[0].priority || a[1] - b[1])
      .map((p) => p[0]);
  }

  function validateInputs(model, data) {
    if (!model.inputs || !model.inputs.length) return;
    const missing = model.inputs.filter((n) => !Object.prototype.hasOwnProperty.call(data, n));
    if (missing.length) {
      throw new ValidationError(
        `model ${pyRepr(model.name)} missing required inputs: [${missing.map(pyRepr).join(", ")}]`
      );
    }
  }

  const nowIso = () => new Date().toISOString().replace("Z", "+00:00");

  function execute(model, data, auditLog) {
    validateInputs(model, data);
    let outcome = model.default_outcome ?? null;
    let matchedRule = null;
    const trace = [];
    for (const rule of orderedRules(model)) {
      const isMatch = ruleMatches(rule, data);
      trace.push({ rule: rule.name, matched: isMatch });
      if (isMatch) { outcome = rule.outcome; matchedRule = rule.name; break; }
    }
    const result = {
      model: model.name,
      outcome,
      matched_rule: matchedRule,
      matched: matchedRule !== null,
      inputs: { ...data },
      trace,
    };
    if (auditLog) {
      auditLog.push({
        timestamp: nowIso(),
        model: model.name,
        inputs: { ...data },
        outcome,
        matched_rule: matchedRule,
      });
    }
    return result;
  }

  // --- composition (mirror dip/composition.py) ----------------------------
  function buildMapper(mapping) {
    if (!mapping) return null;
    if (typeof mapping !== "object" || Array.isArray(mapping)) {
      throw new BadRequest("step 'mapper' must be an object of {target: source}");
    }
    const pairs = Object.entries(mapping);
    return (context) => {
      const out = {};
      for (const [target, source] of pairs) {
        out[target] = source in context ? context[source] : null;
      }
      return out;
    };
  }

  function runFlow(reg, steps, inputs) {
    const flowSteps = [];
    const seen = new Set();
    for (const step of steps) {
      if (step === null || typeof step !== "object" || !("service" in step)) {
        throw new BadRequest("each flow step needs a 'service' (model name)");
      }
      const model = reg.getModel(step.service); // NotFound (404) if missing
      if (seen.has(model.name)) {
        // CompositionError on duplicate → 400 (matches Python's wrapping)
        throw new BadRequest(`duplicate service name in flow: ${pyRepr(model.name)}`);
      }
      seen.add(model.name);
      flowSteps.push({ model, mapper: buildMapper(step.mapper) });
    }
    if (!flowSteps.length) throw new BadRequest("cannot run an empty flow");

    const context = { ...inputs };
    const results = {};
    let finalOutcome;
    try {
      for (const s of flowSteps) {
        const stepInput = s.mapper ? s.mapper(context) : context;
        const res = execute(s.model, stepInput, reg.auditLog);
        results[s.model.name] = res;
        context[`${s.model.name}_outcome`] = res.outcome;
        finalOutcome = res.outcome;
      }
    } catch (e) {
      if (e instanceof DIPError) throw new BadRequest(e.message);
      throw e;
    }
    return { results, context, final_outcome: finalOutcome };
  }

  // --- serialization (mirror app/serialization.py) ------------------------
  const conditionToDict = (c) => ({ field: c.field, operator: c.operator, value: c.value });
  const ruleToDict = (r) => ({
    name: r.name,
    conditions: r.conditions.map(conditionToDict),
    outcome: r.outcome,
    priority: r.priority,
    logic: r.logic,
  });
  const modelToDict = (m) => ({
    name: m.name,
    rules: m.rules.map(ruleToDict),
    default_outcome: m.default_outcome,
    inputs: [...m.inputs],
  });
  const modelSummary = (m) => ({
    name: m.name,
    rule_count: m.rules.length,
    default_outcome: m.default_outcome,
    inputs: [...m.inputs],
  });
  const auditEntryToDict = (e) => ({
    timestamp: e.timestamp,
    model: e.model,
    inputs: e.inputs,
    outcome: e.outcome,
    matched_rule: e.matched_rule,
  });

  function conditionFromDict(d) {
    if (!("operator" in d)) throw new BadRequest("missing required field 'operator'");
    if (!OP_SET.has(d.operator)) {
      throw new BadRequest(`unknown operator ${pyRepr(d.operator)}; expected one of: ${OPERATORS.join(", ")}`);
    }
    if (!("field" in d)) throw new BadRequest("missing required field 'field'");
    return { field: d.field, operator: d.operator, value: d.value ?? null };
  }
  function ruleFromDict(d) {
    const logic = "logic" in d ? d.logic : "all";
    if (logic !== "all" && logic !== "any") {
      throw new BadRequest(`unknown logic ${pyRepr(logic)}; expected 'all' or 'any'`);
    }
    if (!("name" in d)) throw new BadRequest("missing required field 'name'");
    const conditions = (d.conditions || []).map(conditionFromDict);
    const priority = Number.parseInt(d.priority ?? 0, 10);
    return {
      name: d.name,
      conditions,
      outcome: d.outcome ?? null,
      priority: Number.isNaN(priority) ? 0 : priority,
      logic,
    };
  }
  function modelFromDict(d) {
    if (!("name" in d)) throw new BadRequest("missing required field 'name'");
    return {
      name: d.name,
      rules: (d.rules || []).map(ruleFromDict),
      default_outcome: d.default_outcome ?? null,
      inputs: [...(d.inputs || [])],
    };
  }

  // --- seeded models (mirror app/registry.py _sample_models) --------------
  const cond = (field, operator, value) => ({ field, operator, value });
  const rule = (name, conditions, outcome, priority = 0, logic = "all") =>
    ({ name, conditions, outcome, priority, logic });
  const mkModel = (name, inputs, defaultOutcome, rules) =>
    ({ name, inputs, default_outcome: defaultOutcome, rules });

  function sampleModels() {
    return [
      mkModel("credit", ["score", "amount"], "manual_review", [
        rule("auto-decline", [cond("score", "lt", 500)], "decline", 20),
        rule("auto-approve", [cond("score", "gte", 700), cond("amount", "lte", 10000)], "approve", 10),
      ]),
      mkModel("risk", ["amount"], "low", [
        rule("high-risk", [cond("amount", "gte", 10000)], "high"),
      ]),
      mkModel("routing", ["risk"], "auto", [
        rule("to-human", [cond("risk", "eq", "high")], "human"),
      ]),
    ];
  }

  // --- registry (mirror app/registry.py Registry) -------------------------
  function makeRegistry() {
    const models = new Map();
    const auditLog = [];
    for (const m of sampleModels()) models.set(m.name, m);
    return {
      auditLog,
      listModels() { return [...models.values()]; },
      getModel(name) {
        if (!models.has(name)) throw new NotFound(`no model named ${pyRepr(name)}`);
        return models.get(name);
      },
      register(model) { models.set(model.name, model); return model; },
      decide(name, inputs) {
        const model = this.getModel(name); // NotFound (404)
        try { return execute(model, inputs, auditLog); }
        catch (e) { if (e instanceof DIPError) throw new BadRequest(e.message); throw e; }
      },
      runFlow(steps, inputs) { return runFlow(this, steps, inputs); },
    };
  }

  // --- request router (mirror app/api.py Api.handle / _route_api) ---------
  const REG = makeRegistry();

  function need(method, expected) {
    if (method !== expected) throw new MethodNotAllowed(`${method} not allowed; use ${expected}`);
  }
  function jsonObject(body) {
    if (body === undefined || body === null) throw new BadRequest("request body is empty");
    if (typeof body !== "object" || Array.isArray(body)) throw new BadRequest("request body must be a JSON object");
    return body;
  }

  function routeApi(method, path, query, body) {
    if (path === "/api/health") {
      need(method, "GET");
      return { status: "ok", models: REG.listModels().length };
    }
    if (path === "/api/models") {
      if (method === "GET") return REG.listModels().map(modelSummary);
      if (method === "POST") { const m = modelFromDict(jsonObject(body)); REG.register(m); return modelToDict(m); }
      throw new MethodNotAllowed(`${method} not allowed on ${path}`);
    }
    if (path.startsWith("/api/models/")) {
      need(method, "GET");
      const name = decodeURIComponent(path.slice("/api/models/".length));
      return modelToDict(REG.getModel(name));
    }
    if (path === "/api/decide") {
      need(method, "POST");
      const p = jsonObject(body);
      const inputs = p.inputs ?? {};
      if (typeof inputs !== "object" || Array.isArray(inputs)) throw new BadRequest("'inputs' must be a JSON object");
      if (!("model" in p)) throw new BadRequest("missing required field 'model'");
      return REG.decide(p.model, inputs);
    }
    if (path === "/api/flows/run") {
      need(method, "POST");
      const p = jsonObject(body);
      const steps = p.steps;
      if (!Array.isArray(steps) || !steps.length) throw new BadRequest("'steps' must be a non-empty array");
      const inputs = p.inputs ?? {};
      if (typeof inputs !== "object" || Array.isArray(inputs)) throw new BadRequest("'inputs' must be a JSON object");
      return REG.runFlow(steps, inputs);
    }
    if (path === "/api/audit") {
      need(method, "GET");
      const model = query.get("model");
      const entries = model ? REG.auditLog.filter((e) => e.model === model) : REG.auditLog;
      return entries.map(auditEntryToDict);
    }
    throw new NotFound(`no such endpoint: ${path}`);
  }

  function handle(method, rawPath, body) {
    let url;
    try { url = new URL(rawPath, "http://local"); }
    catch (e) { return { status: 400, data: { error: "bad path" } }; }
    const path = url.pathname;
    try {
      if (path === "/api" || path.startsWith("/api/")) {
        return { status: 200, data: routeApi(method, path, url.searchParams, body) };
      }
      throw new NotFound(`no such endpoint: ${path}`);
    } catch (e) {
      if (e instanceof AppError) return { status: e.status, data: { error: e.message } };
      return { status: 500, data: { error: `internal error: ${e.message}` } };
    }
  }

  const api = { handle, _internals: { makeRegistry, execute, applyOp, runFlow, modelFromDict } };
  const root = typeof window !== "undefined" ? window : globalThis;
  root.DIP = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})();
