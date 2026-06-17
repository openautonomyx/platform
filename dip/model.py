"""Decision modeling.

Implements the DIP *Decision modeling* mandatory feature: design explainable,
rule-based decision models with defined inputs, flow and outputs.

A :class:`DecisionModel` is a collection of prioritised :class:`Rule` objects.
Each rule groups one or more :class:`Condition` checks and, when matched,
produces an outcome. Models are plain data, which keeps them inspectable and
explainable — the core promise of a decision model.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping, Sequence

from .errors import ConditionError, ValidationError


class Operator(str, Enum):
    """Comparison operators usable within a :class:`Condition`."""

    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"


# Pure comparison functions keyed by operator. Kept separate from Condition so
# the operator set is easy to audit and extend.
_COMPARATORS: dict[Operator, Callable[[Any, Any], bool]] = {
    Operator.EQ: lambda a, b: a == b,
    Operator.NE: lambda a, b: a != b,
    Operator.GT: lambda a, b: a > b,
    Operator.GTE: lambda a, b: a >= b,
    Operator.LT: lambda a, b: a < b,
    Operator.LTE: lambda a, b: a <= b,
    Operator.IN: lambda a, b: a in b,
    Operator.NOT_IN: lambda a, b: a not in b,
    Operator.CONTAINS: lambda a, b: b in a,
}


class Logic(str, Enum):
    """How a rule combines the results of its conditions."""

    ALL = "all"  # logical AND
    ANY = "any"  # logical OR


@dataclass(frozen=True)
class Condition:
    """A single comparison of an input ``field`` against ``value``."""

    field: str
    operator: Operator
    value: Any

    def evaluate(self, data: Mapping[str, Any]) -> bool:
        """Return whether ``data`` satisfies this condition.

        Raises :class:`ConditionError` if the field is absent or the values
        are not comparable with the chosen operator.
        """
        if self.field not in data:
            raise ConditionError(f"missing input field {self.field!r}")
        actual = data[self.field]
        try:
            return _COMPARATORS[self.operator](actual, self.value)
        except TypeError as exc:
            raise ConditionError(
                f"cannot apply {self.operator.value!r} to "
                f"{actual!r} and {self.value!r}: {exc}"
            ) from exc


@dataclass(frozen=True)
class Rule:
    """A named group of conditions that yields ``outcome`` when matched.

    A rule with no conditions always matches, which makes it a convenient
    catch-all/default when given a low priority.
    """

    name: str
    conditions: tuple[Condition, ...] = ()
    outcome: Any = None
    priority: int = 0  # higher priority rules are evaluated first
    logic: Logic = Logic.ALL

    def matches(self, data: Mapping[str, Any]) -> bool:
        """Return whether ``data`` satisfies this rule's conditions."""
        results = [c.evaluate(data) for c in self.conditions]
        if self.logic is Logic.ALL:
            return all(results)
        return any(results)


@dataclass
class DecisionModel:
    """An explainable, prioritised collection of rules.

    :param inputs: optional declared input field names. When non-empty the
        engine validates that every declared input is present before execution.
    :param default_outcome: outcome returned when no rule matches.
    """

    name: str
    rules: list[Rule] = field(default_factory=list)
    default_outcome: Any = None
    inputs: tuple[str, ...] = ()

    def ordered_rules(self) -> list[Rule]:
        """Rules sorted by descending priority (stable for equal priorities)."""
        return sorted(self.rules, key=lambda r: r.priority, reverse=True)

    def validate_inputs(self, data: Mapping[str, Any]) -> None:
        """Ensure all declared inputs are present in ``data``.

        No-op when ``inputs`` is empty (i.e. inputs are not declared).
        Raises :class:`ValidationError` listing any missing fields.
        """
        if not self.inputs:
            return
        missing = [name for name in self.inputs if name not in data]
        if missing:
            raise ValidationError(
                f"model {self.name!r} missing required inputs: {missing}"
            )


def all_of(*conditions: Condition) -> tuple[Condition, ...]:
    """Convenience helper to build a tuple of conditions."""
    return tuple(conditions)
