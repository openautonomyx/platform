"use strict";
/*
 * Parity check for the in-browser engine (site/engine.js) against the behaviour
 * of the Python dip engine + app API. Run before every Pages deploy so the
 * static build can never ship a regression in the ported logic.
 */
const DIP = require("../site/engine.js");

let pass = 0;
const failures = [];
function check(name, cond, detail) {
  if (cond) { pass++; }
  else { failures.push(`${name}${detail ? " — " + detail : ""}`); }
}
function call(method, path, body) { return DIP.handle(method, path, body); }
function ok(method, path, body) {
  const r = call(method, path, body);
  if (r.status >= 400) throw new Error(`unexpected ${r.status} for ${method} ${path}: ${r.data && r.data.error}`);
  return r.data;
}

// 1. health
const health = call("GET", "/api/health");
check("health ok", health.status === 200 && health.data.models === 3, JSON.stringify(health.data));

// 2. list models
const models = ok("GET", "/api/models");
check("3 seeded models", models.length === 3);
check("model names", models.map((m) => m.name).sort().join(",") === "credit,risk,routing");
const credit = models.find((m) => m.name === "credit");
check("credit rule_count", credit && credit.rule_count === 2);
check("credit inputs", credit && credit.inputs.join(",") === "score,amount");

// 3. model detail
const creditFull = ok("GET", "/api/models/credit");
check("credit detail rules", creditFull.rules.length === 2);
check("credit rule order preserved", creditFull.rules[0].name === "auto-decline");

// 4. decide → approve (high score, low amount)
const approve = ok("POST", "/api/decide", { model: "credit", inputs: { score: 750, amount: 5000 } });
check("approve outcome", approve.outcome === "approve", approve.outcome);
check("approve matched", approve.matched === true && approve.matched_rule === "auto-approve");
check("approve trace", approve.trace.length === 2 &&
  approve.trace[0].rule === "auto-decline" && approve.trace[0].matched === false &&
  approve.trace[1].rule === "auto-approve" && approve.trace[1].matched === true,
  JSON.stringify(approve.trace));

// 5. decide → decline (low score) — first match wins, trace stops
const decline = ok("POST", "/api/decide", { model: "credit", inputs: { score: 450, amount: 5000 } });
check("decline outcome", decline.outcome === "decline" && decline.matched_rule === "auto-decline");
check("decline short-circuits trace", decline.trace.length === 1, JSON.stringify(decline.trace));

// 6. decide → default (no rule matches)
const review = ok("POST", "/api/decide", { model: "credit", inputs: { score: 600, amount: 5000 } });
check("default outcome", review.outcome === "manual_review" && review.matched === false);
check("default trace evaluates all", review.trace.length === 2 && review.trace.every((s) => !s.matched));

// 7. decide → validation error (missing declared input) → 400
const missing = call("POST", "/api/decide", { model: "credit", inputs: { score: 750 } });
check("missing input → 400", missing.status === 400, String(missing.status));
check("missing input message", /missing required inputs: \['amount'\]/.test(missing.data.error || ""), missing.data.error);

// 8. flow risk → routing (mapper feeds risk outcome forward)
const flow = ok("POST", "/api/flows/run", {
  steps: [{ service: "risk" }, { service: "routing", mapper: { risk: "risk_outcome" } }],
  inputs: { amount: 50000 },
});
check("flow risk=high", flow.results.risk.outcome === "high");
check("flow routing=human", flow.results.routing.outcome === "human");
check("flow final_outcome", flow.final_outcome === "human", flow.final_outcome);
// The mapper shapes the *next step's input* separately; only `<service>_outcome`
// is written back to the shared context (mirrors dip.composition.DecisionFlow.run).
check("flow context wired", flow.context.risk_outcome === "high" && flow.context.routing_outcome === "human",
  JSON.stringify(flow.context));

// 9. flow low-risk path → routing default
const flowLow = ok("POST", "/api/flows/run", {
  steps: [{ service: "risk" }, { service: "routing", mapper: { risk: "risk_outcome" } }],
  inputs: { amount: 100 },
});
check("flow low → auto", flowLow.final_outcome === "auto", flowLow.final_outcome);

// 10. audit log accumulates + filters
const allAudit = ok("GET", "/api/audit");
check("audit recorded", allAudit.length >= 7, String(allAudit.length)); // 3 decides + 4 flow steps so far
const creditAudit = ok("GET", "/api/audit?model=credit");
check("audit filter by model", creditAudit.length === 3 && creditAudit.every((e) => e.model === "credit"),
  String(creditAudit.length));
check("audit timestamp shape", /\+00:00$/.test(allAudit[0].timestamp), allAudit[0].timestamp);

// 11. register a model, then decide against it
const kyc = ok("POST", "/api/models", {
  name: "kyc", inputs: ["country", "pep"], default_outcome: "review",
  rules: [
    { name: "block-sanctioned", priority: 30, conditions: [{ field: "country", operator: "in", value: ["XX", "YY"] }], outcome: "block" },
    { name: "clear-low-risk", priority: 10, conditions: [{ field: "pep", operator: "eq", value: false }], outcome: "clear" },
  ],
});
check("kyc registered", kyc.name === "kyc" && kyc.rules.length === 2);
check("models now 4", ok("GET", "/api/models").length === 4);
const kycBlock = ok("POST", "/api/decide", { model: "kyc", inputs: { country: "XX", pep: false } });
check("kyc in-operator block", kycBlock.outcome === "block", kycBlock.outcome);
const kycClear = ok("POST", "/api/decide", { model: "kyc", inputs: { country: "US", pep: false } });
check("kyc clear (eq false)", kycClear.outcome === "clear", kycClear.outcome);
const kycReview = ok("POST", "/api/decide", { model: "kyc", inputs: { country: "US", pep: true } });
check("kyc default review", kycReview.outcome === "review" && kycReview.matched === false);

// 12. bad operator on register → 400
const badOp = call("POST", "/api/models", { name: "x", rules: [{ name: "r", conditions: [{ field: "a", operator: "zz" }], outcome: 1 }] });
check("unknown operator → 400", badOp.status === 400 && /unknown operator/.test(badOp.data.error || ""));

// 13. unknown model → 404
const noModel = call("POST", "/api/decide", { model: "nope", inputs: {} });
check("unknown model → 404", noModel.status === 404, String(noModel.status));

// 14. unknown endpoint → 404
check("unknown endpoint → 404", call("GET", "/api/nope").status === 404);

// --- report ---------------------------------------------------------------
console.log(`engine parity checks: ${pass} passed, ${failures.length} failed`);
if (failures.length) {
  for (const f of failures) console.error("  ✗ " + f);
  process.exit(1);
}
console.log("✓ in-browser engine matches the Python engine's behaviour");
