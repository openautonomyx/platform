"""Application state: the decision models, the shared audit log, the engine.

The :class:`Registry` is the in-memory home for everything the console operates
on. A single :class:`~dip.AuditLog` is wired into one :class:`~dip.DecisionEngine`
so that *every* decision — whether run directly or as part of an orchestrated
flow — is recorded for governance. A few example models are seeded so the app
is useful the moment it starts.
"""
from __future__ import annotations

import threading
from typing import Any, Callable, Mapping, Sequence

from dip import (
    AuditLog,
    Condition,
    DecisionEngine,
    DecisionFlow,
    DecisionModel,
    DecisionResult,
    DecisionService,
    Operator,
    Rule,
)
from dip.composition import FlowResult, StepMapper
from dip.errors import DIPError

from .errors import BadRequest, NotFound


class Registry:
    """Thread-safe store of decision models plus shared governance state."""

    def __init__(self, seed: bool = True) -> None:
        self._lock = threading.Lock()
        self._models: dict[str, DecisionModel] = {}
        self.audit_log = AuditLog()
        self.engine = DecisionEngine(audit_log=self.audit_log)
        if seed:
            for model in _sample_models():
                self._models[model.name] = model

    # --- model management -------------------------------------------------

    def list_models(self) -> list[DecisionModel]:
        with self._lock:
            return list(self._models.values())

    def get_model(self, name: str) -> DecisionModel:
        with self._lock:
            try:
                return self._models[name]
            except KeyError:
                raise NotFound(f"no model named {name!r}") from None

    def register(self, model: DecisionModel) -> DecisionModel:
        """Add or replace a model, keyed by name."""
        with self._lock:
            self._models[model.name] = model
        return model

    # --- execution --------------------------------------------------------

    def decide(self, name: str, inputs: Mapping[str, Any]) -> DecisionResult:
        model = self.get_model(name)
        try:
            return self.engine.execute(model, inputs)
        except DIPError as exc:
            # Engine validation/condition errors are the caller's fault → 400.
            raise BadRequest(str(exc)) from exc

    def run_flow(
        self, steps: Sequence[Mapping[str, Any]], inputs: Mapping[str, Any]
    ) -> FlowResult:
        """Build and run a :class:`~dip.DecisionFlow` from a declarative spec.

        Each step is ``{"service": <model name>, "mapper": {target: source}}``.
        The optional ``mapper`` shapes the running flow context into the inputs
        the step's model expects (e.g. ``{"risk": "risk_outcome"}``), mirroring
        the engine's callable mappers but in plain JSON.
        """
        flow = DecisionFlow()
        for step in steps:
            if "service" not in step:
                raise BadRequest("each flow step needs a 'service' (model name)")
            service = DecisionService(self.get_model(step["service"]), self.engine)
            try:
                flow.add(service, _build_mapper(step.get("mapper")))
            except DIPError as exc:
                raise BadRequest(str(exc)) from exc
        try:
            return flow.run(inputs)
        except DIPError as exc:
            raise BadRequest(str(exc)) from exc


def _build_mapper(mapping: Mapping[str, str] | None) -> StepMapper | None:
    """Turn a ``{target: source}`` dict into a flow step mapper callable."""
    if not mapping:
        return None
    if not isinstance(mapping, dict):
        raise BadRequest("step 'mapper' must be an object of {target: source}")
    pairs = dict(mapping)

    def mapper(context: dict[str, Any]) -> dict[str, Any]:
        return {target: context.get(source) for target, source in pairs.items()}

    return mapper


def _sample_models() -> list[DecisionModel]:
    """Example models so the console is immediately explorable.

    ``credit`` mirrors the example in ``dip/README.md``; ``risk`` and
    ``routing`` are designed to be chained in a flow (risk feeds routing),
    matching the composition tests.
    """
    credit = DecisionModel(
        name="credit",
        inputs=("score", "amount"),
        default_outcome="manual_review",
        rules=[
            Rule(
                "auto-decline",
                (Condition("score", Operator.LT, 500),),
                outcome="decline",
                priority=20,
            ),
            Rule(
                "auto-approve",
                (
                    Condition("score", Operator.GTE, 700),
                    Condition("amount", Operator.LTE, 10_000),
                ),
                outcome="approve",
                priority=10,
            ),
        ],
    )
    risk = DecisionModel(
        name="risk",
        inputs=("amount",),
        default_outcome="low",
        rules=[
            Rule(
                "high-risk",
                (Condition("amount", Operator.GTE, 10_000),),
                outcome="high",
            )
        ],
    )
    routing = DecisionModel(
        name="routing",
        inputs=("risk",),
        default_outcome="auto",
        rules=[
            Rule(
                "to-human",
                (Condition("risk", Operator.EQ, "high"),),
                outcome="human",
            )
        ],
    )
    return [credit, risk, routing]
