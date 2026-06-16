"""Decision service composition.

Implements the DIP *Decision service composition* mandatory feature:
componentise decision flows into modular, reusable :class:`DecisionService`
units and orchestrate them as a :class:`DecisionFlow`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .engine import DecisionEngine, DecisionResult
from .errors import CompositionError
from .model import DecisionModel


class DecisionService:
    """A reusable, named decision component wrapping a model and an engine."""

    def __init__(self, model: DecisionModel, engine: DecisionEngine | None = None) -> None:
        self.model = model
        self.engine = engine or DecisionEngine()

    @property
    def name(self) -> str:
        return self.model.name

    def decide(self, data: Mapping[str, Any]) -> DecisionResult:
        """Execute this service's model against ``data``."""
        return self.engine.execute(self.model, data)


# A mapper turns the running flow context into the input data for the next step.
StepMapper = Callable[[dict[str, Any]], Mapping[str, Any]]


@dataclass(frozen=True)
class FlowStep:
    """A single step in a :class:`DecisionFlow`."""

    service: DecisionService
    mapper: StepMapper | None = None  # defaults to passing the context through


@dataclass(frozen=True)
class FlowResult:
    """The aggregate result of running a :class:`DecisionFlow`."""

    results: dict[str, DecisionResult]
    context: dict[str, Any]

    @property
    def final_outcome(self) -> Any:
        """Outcome of the last step that ran."""
        if not self.results:
            raise CompositionError("flow produced no results")
        return next(reversed(self.results.values())).outcome


class DecisionFlow:
    """Orchestrates a sequence of decision services.

    Each step receives a shared, mutable ``context`` (seeded from the flow's
    input). After a step runs, its outcome is written back to the context under
    ``"<service>_outcome"`` so downstream steps can consume it. A step may
    supply a ``mapper`` to shape the context into the inputs its model expects.
    """

    def __init__(self) -> None:
        self._steps: list[FlowStep] = []

    def add(self, service: DecisionService, mapper: StepMapper | None = None) -> "DecisionFlow":
        """Append a service to the flow. Returns self for chaining."""
        if any(s.service.name == service.name for s in self._steps):
            raise CompositionError(f"duplicate service name in flow: {service.name!r}")
        self._steps.append(FlowStep(service=service, mapper=mapper))
        return self

    def run(self, data: Mapping[str, Any]) -> FlowResult:
        """Execute every step in order and collect their results."""
        if not self._steps:
            raise CompositionError("cannot run an empty flow")

        context: dict[str, Any] = dict(data)
        results: dict[str, DecisionResult] = {}

        for step in self._steps:
            step_input = step.mapper(context) if step.mapper else context
            result = step.service.decide(step_input)
            results[step.service.name] = result
            context[f"{step.service.name}_outcome"] = result.outcome

        return FlowResult(results=results, context=context)
