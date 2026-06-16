"""Tests for decision monitoring & governance (the audit log)."""
from datetime import datetime, timezone

from dip import (
    AuditLog,
    Condition,
    DecisionEngine,
    DecisionModel,
    Operator,
    Rule,
)


def _fixed_clock():
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _simple_model() -> DecisionModel:
    return DecisionModel(
        name="discount",
        default_outcome="none",
        rules=[
            Rule(
                name="vip",
                conditions=(Condition("tier", Operator.EQ, "gold"),),
                outcome="10%",
            )
        ],
    )


def test_engine_records_each_execution():
    log = AuditLog(clock=_fixed_clock)
    engine = DecisionEngine(audit_log=log)
    model = _simple_model()

    engine.execute(model, {"tier": "gold"})
    engine.execute(model, {"tier": "silver"})

    assert len(log) == 2
    first, second = log.entries
    assert first.outcome == "10%"
    assert first.matched_rule == "vip"
    assert second.outcome == "none"
    assert second.matched_rule is None


def test_audit_entry_uses_injected_clock():
    log = AuditLog(clock=_fixed_clock)
    engine = DecisionEngine(audit_log=log)
    engine.execute(_simple_model(), {"tier": "gold"})
    assert log.entries[0].timestamp == _fixed_clock()


def test_audit_inputs_are_independent_copies():
    log = AuditLog(clock=_fixed_clock)
    engine = DecisionEngine(audit_log=log)
    data = {"tier": "gold"}
    engine.execute(_simple_model(), data)
    data["tier"] = "bronze"
    assert log.entries[0].inputs == {"tier": "gold"}


def test_for_model_filters_by_name():
    log = AuditLog(clock=_fixed_clock)
    engine = DecisionEngine(audit_log=log)
    engine.execute(_simple_model(), {"tier": "gold"})
    engine.execute(DecisionModel(name="other"), {})
    assert len(log.for_model("discount")) == 1
    assert len(log.for_model("other")) == 1


def test_filter_with_predicate():
    log = AuditLog(clock=_fixed_clock)
    engine = DecisionEngine(audit_log=log)
    engine.execute(_simple_model(), {"tier": "gold"})
    engine.execute(_simple_model(), {"tier": "silver"})
    matched = log.filter(lambda e: e.matched_rule is not None)
    assert len(matched) == 1
    assert matched[0].outcome == "10%"


def test_no_audit_log_means_no_recording():
    # Engine without a log should simply not raise.
    engine = DecisionEngine()
    result = engine.execute(_simple_model(), {"tier": "gold"})
    assert result.outcome == "10%"
