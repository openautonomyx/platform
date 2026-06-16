"""Tests for decision modeling (conditions, rules, models)."""
import pytest

from dip import Condition, DecisionModel, Logic, Operator, Rule, all_of
from dip.errors import ConditionError, ValidationError


# --- Condition.evaluate -----------------------------------------------------

@pytest.mark.parametrize(
    "operator, value, actual, expected",
    [
        (Operator.EQ, 5, 5, True),
        (Operator.EQ, 5, 4, False),
        (Operator.NE, 5, 4, True),
        (Operator.GT, 10, 11, True),
        (Operator.GT, 10, 10, False),
        (Operator.GTE, 10, 10, True),
        (Operator.LT, 10, 9, True),
        (Operator.LTE, 10, 10, True),
        (Operator.IN, [1, 2, 3], 2, True),
        (Operator.IN, [1, 2, 3], 9, False),
        (Operator.NOT_IN, [1, 2, 3], 9, True),
        (Operator.CONTAINS, "gold", "premium-gold", True),
        (Operator.CONTAINS, "gold", "premium-silver", False),
    ],
)
def test_condition_operators(operator, value, actual, expected):
    cond = Condition(field="x", operator=operator, value=value)
    assert cond.evaluate({"x": actual}) is expected


def test_condition_missing_field_raises():
    cond = Condition("amount", Operator.GT, 100)
    with pytest.raises(ConditionError, match="missing input field 'amount'"):
        cond.evaluate({"other": 1})


def test_condition_incomparable_types_raises():
    cond = Condition("amount", Operator.GT, 100)
    with pytest.raises(ConditionError, match="cannot apply 'gt'"):
        cond.evaluate({"amount": "not-a-number"})


# --- Rule.matches -----------------------------------------------------------

def test_rule_all_logic_is_and():
    rule = Rule(
        name="big-spender",
        conditions=all_of(
            Condition("amount", Operator.GTE, 1000),
            Condition("region", Operator.EQ, "EU"),
        ),
        outcome="review",
    )
    assert rule.matches({"amount": 1500, "region": "EU"}) is True
    assert rule.matches({"amount": 1500, "region": "US"}) is False


def test_rule_any_logic_is_or():
    rule = Rule(
        name="flag",
        conditions=all_of(
            Condition("amount", Operator.GTE, 1000),
            Condition("blacklisted", Operator.EQ, True),
        ),
        outcome="block",
        logic=Logic.ANY,
    )
    assert rule.matches({"amount": 10, "blacklisted": True}) is True
    assert rule.matches({"amount": 10, "blacklisted": False}) is False


def test_rule_without_conditions_always_matches():
    # A condition-less rule acts as a catch-all default.
    rule = Rule(name="default", outcome="approve")
    assert rule.matches({}) is True


# --- DecisionModel ----------------------------------------------------------

def test_ordered_rules_sorts_by_priority_desc():
    low = Rule(name="low", priority=1)
    high = Rule(name="high", priority=10)
    mid = Rule(name="mid", priority=5)
    model = DecisionModel(name="m", rules=[low, high, mid])
    assert [r.name for r in model.ordered_rules()] == ["high", "mid", "low"]


def test_ordered_rules_is_stable_for_equal_priority():
    a = Rule(name="a", priority=0)
    b = Rule(name="b", priority=0)
    model = DecisionModel(name="m", rules=[a, b])
    assert [r.name for r in model.ordered_rules()] == ["a", "b"]


def test_validate_inputs_passes_when_all_present():
    model = DecisionModel(name="m", inputs=("amount", "region"))
    model.validate_inputs({"amount": 1, "region": "EU"})  # no raise


def test_validate_inputs_raises_listing_missing():
    model = DecisionModel(name="m", inputs=("amount", "region"))
    with pytest.raises(ValidationError, match="region"):
        model.validate_inputs({"amount": 1})


def test_validate_inputs_noop_when_not_declared():
    model = DecisionModel(name="m")  # no declared inputs
    model.validate_inputs({})  # no raise
