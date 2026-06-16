"""Tests for decision service composition (services and flows)."""
import pytest

from dip import (
    AuditLog,
    Condition,
    DecisionEngine,
    DecisionFlow,
    DecisionModel,
    DecisionService,
    Operator,
    Rule,
)
from dip.errors import CompositionError


def _risk_model() -> DecisionModel:
    return DecisionModel(
        name="risk",
        default_outcome="low",
        rules=[
            Rule(
                name="high-risk",
                conditions=(Condition("amount", Operator.GTE, 10_000),),
                outcome="high",
            )
        ],
    )


def _routing_model() -> DecisionModel:
    return DecisionModel(
        name="routing",
        default_outcome="auto",
        rules=[
            Rule(
                name="to-human",
                conditions=(Condition("risk", Operator.EQ, "high"),),
                outcome="human",
            )
        ],
    )


def test_service_decide_delegates_to_engine():
    service = DecisionService(_risk_model())
    result = service.decide({"amount": 50_000})
    assert result.outcome == "high"
    assert service.name == "risk"


def test_flow_runs_steps_in_order_and_passes_context():
    flow = (
        DecisionFlow()
        .add(DecisionService(_risk_model()))
        # map the risk service's outcome into the routing model's input
        .add(
            DecisionService(_routing_model()),
            mapper=lambda ctx: {"risk": ctx["risk_outcome"]},
        )
    )

    result = flow.run({"amount": 50_000})

    assert result.results["risk"].outcome == "high"
    assert result.results["routing"].outcome == "human"
    assert result.final_outcome == "human"


def test_flow_low_risk_routes_to_auto():
    flow = (
        DecisionFlow()
        .add(DecisionService(_risk_model()))
        .add(
            DecisionService(_routing_model()),
            mapper=lambda ctx: {"risk": ctx["risk_outcome"]},
        )
    )
    result = flow.run({"amount": 100})
    assert result.final_outcome == "auto"


def test_flow_shares_one_audit_log_across_services():
    log = AuditLog()
    engine = DecisionEngine(audit_log=log)
    flow = (
        DecisionFlow()
        .add(DecisionService(_risk_model(), engine))
        .add(
            DecisionService(_routing_model(), engine),
            mapper=lambda ctx: {"risk": ctx["risk_outcome"]},
        )
    )
    flow.run({"amount": 50_000})
    # both steps recorded to the shared governance log
    assert len(log) == 2
    assert {e.model for e in log.entries} == {"risk", "routing"}


def test_duplicate_service_name_rejected():
    flow = DecisionFlow().add(DecisionService(_risk_model()))
    with pytest.raises(CompositionError, match="duplicate"):
        flow.add(DecisionService(_risk_model()))


def test_empty_flow_cannot_run():
    with pytest.raises(CompositionError, match="empty flow"):
        DecisionFlow().run({})


def test_final_outcome_on_empty_results_raises():
    from dip import FlowResult

    with pytest.raises(CompositionError, match="no results"):
        FlowResult(results={}, context={}).final_outcome
