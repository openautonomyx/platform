"""Decision execution.

Implements the DIP *Decision execution* mandatory feature: orchestrate and
execute a decision model against input data, producing an explainable result
and (optionally) recording it for governance.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .governance import AuditLog
from .model import DecisionModel


@dataclass(frozen=True)
class TraceStep:
    """One evaluated rule in a decision trace (supports explainability)."""

    rule: str
    matched: bool


@dataclass(frozen=True)
class DecisionResult:
    """The outcome of executing a model, with a trace for explainability."""

    model: str
    outcome: Any
    matched_rule: str | None
    inputs: dict[str, Any]
    trace: tuple[TraceStep, ...] = field(default_factory=tuple)

    @property
    def matched(self) -> bool:
        """Whether any rule matched (vs. falling back to the default)."""
        return self.matched_rule is not None


class DecisionEngine:
    """Executes decision models and records results to an optional audit log."""

    def __init__(self, audit_log: AuditLog | None = None) -> None:
        self.audit_log = audit_log

    def execute(self, model: DecisionModel, data: Mapping[str, Any]) -> DecisionResult:
        """Evaluate ``model`` against ``data`` and return a :class:`DecisionResult`.

        Rules are evaluated in descending priority order; the first match wins.
        If no rule matches, the model's ``default_outcome`` is returned. When an
        audit log is configured, the result is recorded before being returned.
        """
        model.validate_inputs(data)

        outcome = model.default_outcome
        matched_rule: str | None = None
        trace: list[TraceStep] = []

        for rule in model.ordered_rules():
            is_match = rule.matches(data)
            trace.append(TraceStep(rule=rule.name, matched=is_match))
            if is_match:
                outcome = rule.outcome
                matched_rule = rule.name
                break

        result = DecisionResult(
            model=model.name,
            outcome=outcome,
            matched_rule=matched_rule,
            inputs=dict(data),
            trace=tuple(trace),
        )

        if self.audit_log is not None:
            self.audit_log.record(result)

        return result
