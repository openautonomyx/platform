"""HTTP-aware error types for the app layer.

Each error carries the HTTP ``status`` the API should return for it, so the
router can translate any raised :class:`AppError` into a JSON error response
without a pile of ``try``/``except`` branches.
"""
from __future__ import annotations


class AppError(Exception):
    """Base class for app errors. Subclasses set the HTTP ``status``."""

    status = 500


class BadRequest(AppError):
    """The request was malformed (bad JSON, missing fields, invalid values)."""

    status = 400


class NotFound(AppError):
    """The requested resource (model, endpoint, file) does not exist."""

    status = 404


class MethodNotAllowed(AppError):
    """The HTTP method is not supported for this endpoint."""

    status = 405
