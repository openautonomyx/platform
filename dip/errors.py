"""Exception hierarchy for the Decision Intelligence Platform (DIP) module."""
from __future__ import annotations


class DIPError(Exception):
    """Base class for all DIP errors."""


class ConditionError(DIPError):
    """Raised when a condition cannot be evaluated against the supplied data."""


class ValidationError(DIPError):
    """Raised when input data does not satisfy a model's declared inputs."""


class CompositionError(DIPError):
    """Raised when a decision flow is misconfigured or a step fails."""
