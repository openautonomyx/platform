"""Decision Intelligence Platform (DIP) — a small, explainable decision engine.

This package implements the mandatory DIP capabilities described in the repo's
``features`` file:

* **Decision modeling** — :mod:`dip.model` (:class:`DecisionModel`, :class:`Rule`,
  :class:`Condition`).
* **Decision execution** — :mod:`dip.engine` (:class:`DecisionEngine`,
  :class:`DecisionResult`).
* **Decision service composition** — :mod:`dip.composition`
  (:class:`DecisionService`, :class:`DecisionFlow`).
* **Decision monitoring & governance** — :mod:`dip.governance`
  (:class:`AuditLog`, :class:`AuditEntry`).
"""
from __future__ import annotations

from .composition import DecisionFlow, DecisionService, FlowResult, FlowStep
from .engine import DecisionEngine, DecisionResult, TraceStep
from .errors import (
    CompositionError,
    ConditionError,
    DIPError,
    ValidationError,
)
from .governance import AuditEntry, AuditLog
from .model import (
    Condition,
    DecisionModel,
    Logic,
    Operator,
    Rule,
    all_of,
)

__all__ = [
    # modeling
    "Condition",
    "DecisionModel",
    "Logic",
    "Operator",
    "Rule",
    "all_of",
    # execution
    "DecisionEngine",
    "DecisionResult",
    "TraceStep",
    # composition
    "DecisionFlow",
    "DecisionService",
    "FlowResult",
    "FlowStep",
    # governance
    "AuditEntry",
    "AuditLog",
    # errors
    "DIPError",
    "ConditionError",
    "ValidationError",
    "CompositionError",
]

__version__ = "0.1.0"
