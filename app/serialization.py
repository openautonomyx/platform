"""Translate between the :mod:`dip` engine's dataclasses and plain JSON dicts.

The web app speaks JSON over HTTP while the engine speaks dataclasses and
enums. Keeping every conversion here means the API and the engine stay
decoupled, and there is exactly one place to look when the wire format changes.
"""
from __future__ import annotations

from typing import Any, Mapping

from dip import Condition, DecisionModel, DecisionResult, Logic, Operator, Rule
from dip.composition import FlowResult
from dip.governance import AuditEntry

from .errors import BadRequest


def _require(d: Mapping[str, Any], key: str) -> Any:
    if key not in d:
        raise BadRequest(f"missing required field {key!r}")
    return d[key]


# --- conditions -----------------------------------------------------------

def condition_to_dict(c: Condition) -> dict[str, Any]:
    return {"field": c.field, "operator": c.operator.value, "value": c.value}


def condition_from_dict(d: Mapping[str, Any]) -> Condition:
    raw_op = _require(d, "operator")
    try:
        operator = Operator(raw_op)
    except ValueError as exc:
        valid = ", ".join(op.value for op in Operator)
        raise BadRequest(f"unknown operator {raw_op!r}; expected one of: {valid}") from exc
    return Condition(field=_require(d, "field"), operator=operator, value=d.get("value"))


# --- rules ----------------------------------------------------------------

def rule_to_dict(r: Rule) -> dict[str, Any]:
    return {
        "name": r.name,
        "conditions": [condition_to_dict(c) for c in r.conditions],
        "outcome": r.outcome,
        "priority": r.priority,
        "logic": r.logic.value,
    }


def rule_from_dict(d: Mapping[str, Any]) -> Rule:
    raw_logic = d.get("logic", Logic.ALL.value)
    try:
        logic = Logic(raw_logic)
    except ValueError as exc:
        raise BadRequest(f"unknown logic {raw_logic!r}; expected 'all' or 'any'") from exc
    conditions = tuple(condition_from_dict(c) for c in d.get("conditions", ()))
    return Rule(
        name=_require(d, "name"),
        conditions=conditions,
        outcome=d.get("outcome"),
        priority=int(d.get("priority", 0)),
        logic=logic,
    )


# --- models ---------------------------------------------------------------

def model_to_dict(m: DecisionModel) -> dict[str, Any]:
    return {
        "name": m.name,
        "rules": [rule_to_dict(r) for r in m.rules],
        "default_outcome": m.default_outcome,
        "inputs": list(m.inputs),
    }


def model_summary(m: DecisionModel) -> dict[str, Any]:
    """A lightweight view for list endpoints (no rule bodies)."""
    return {
        "name": m.name,
        "rule_count": len(m.rules),
        "default_outcome": m.default_outcome,
        "inputs": list(m.inputs),
    }


def model_from_dict(d: Mapping[str, Any]) -> DecisionModel:
    rules = [rule_from_dict(r) for r in d.get("rules", ())]
    return DecisionModel(
        name=_require(d, "name"),
        rules=rules,
        default_outcome=d.get("default_outcome"),
        inputs=tuple(d.get("inputs", ())),
    )


# --- results & audit ------------------------------------------------------

def result_to_dict(r: DecisionResult) -> dict[str, Any]:
    return {
        "model": r.model,
        "outcome": r.outcome,
        "matched_rule": r.matched_rule,
        "matched": r.matched,
        "inputs": r.inputs,
        "trace": [{"rule": s.rule, "matched": s.matched} for s in r.trace],
    }


def audit_entry_to_dict(e: AuditEntry) -> dict[str, Any]:
    return {
        "timestamp": e.timestamp.isoformat(),
        "model": e.model,
        "inputs": e.inputs,
        "outcome": e.outcome,
        "matched_rule": e.matched_rule,
    }


def flow_result_to_dict(fr: FlowResult) -> dict[str, Any]:
    return {
        "results": {name: result_to_dict(res) for name, res in fr.results.items()},
        "context": fr.context,
        "final_outcome": fr.final_outcome,
    }
