"""Tests for decision execution (the engine)."""
import pytest

from dip import (
    Condition,
    DecisionEngine,
    DecisionModel,
    Operator,
    Rule,
)
from dip.errors import ValidationError


@pytest.fixture
def credit_model() -> DecisionModel:
    """A small loan-decision model used across several tests."""
    return DecisionModel(
        name="credit",
        inputs=("score", "amount"),
        default_outcome="manual_review",
        rules=[
            Rule(
                name="auto-approve",
                conditions=(
                    Condition("score", Operator.GTE, 700),
                    Condition("amount", Operator.LTE, 10_000),
                ),
                outcome="approve",
                priority=10,
            ),
            Rule(
                name="auto-decline",
                conditions=(Condition("score", Operator.LT, 500),),
                outcome="decline",
                priority=20,
            ),
        ],
    )


def test_first_matching_rule_wins(credit_model):
    engine = DecisionEngine()
    result = engine.execute(credit_model, {"score": 750, "amount": 5_000})
    assert result.outcome == "approve"
    assert result.matched_rule == "auto-approve"
    assert result.matched is True


def test_priority_decides_between_competing_rules(credit_model):
    # score < 500 matches decline; decline has higher priority so it wins
    engine = DecisionEngine()
    result = engine.execute(credit_model, {"score": 450, "amount": 1_000})
    assert result.outcome == "decline"
    assert result.matched_rule == "auto-decline"


def test_default_outcome_when_no_rule_matches(credit_model):
    engine = DecisionEngine()
    result = engine.execute(credit_model, {"score": 600, "amount": 50_000})
    assert result.outcome == "manual_review"
    assert result.matched_rule is None
    assert result.matched is False


def test_trace_records_evaluated_rules(credit_model):
    engine = DecisionEngine()
    result = engine.execute(credit_model, {"score": 750, "amount": 5_000})
    # decline (priority 20) is evaluated first and fails, then approve matches.
    assert [(s.rule, s.matched) for s in result.trace] == [
        ("auto-decline", False),
        ("auto-approve", True),
    ]


def test_inputs_are_snapshotted_not_aliased(credit_model):
    engine = DecisionEngine()
    data = {"score": 750, "amount": 5_000}
    result = engine.execute(credit_model, data)
    data["score"] = 0
    assert result.inputs == {"score": 750, "amount": 5_000}


def test_missing_declared_input_raises(credit_model):
    engine = DecisionEngine()
    with pytest.raises(ValidationError, match="amount"):
        engine.execute(credit_model, {"score": 750})
