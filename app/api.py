"""Transport-independent request router for the console.

:class:`Api` maps ``(method, path, body)`` to a :class:`Response`. It has no
dependency on sockets or :mod:`http.server`, so the whole API surface can be
exercised in unit tests by calling :meth:`Api.handle` directly.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, unquote, urlsplit

from . import serialization as ser
from .errors import AppError, BadRequest, MethodNotAllowed, NotFound
from .registry import Registry

STATIC_DIR = Path(__file__).parent / "static"

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
}

_JSON = "application/json; charset=utf-8"


@dataclass
class Response:
    """A fully-formed HTTP response, ready for any transport to write out."""

    status: int
    body: bytes
    content_type: str = _JSON

    def json(self) -> Any:
        """Decode the body as JSON (convenience for tests)."""
        return json.loads(self.body)


class Api:
    """Routes requests to the decision engine and the static UI."""

    def __init__(self, registry: Registry | None = None) -> None:
        self.registry = registry or Registry()

    def handle(self, method: str, raw_path: str, body: bytes = b"") -> Response:
        parts = urlsplit(raw_path)
        path = parts.path
        query = parse_qs(parts.query)
        try:
            if path == "/api" or path.startswith("/api/"):
                return _json(self._route_api(method, path, query, body))
            return self._serve_static(method, path)
        except AppError as exc:
            return _json({"error": str(exc)}, status=exc.status)
        except Exception as exc:  # noqa: BLE001 — never leak a traceback to the client
            return _json({"error": f"internal error: {exc}"}, status=500)

    # --- API routing ------------------------------------------------------

    def _route_api(
        self, method: str, path: str, query: Mapping[str, list[str]], body: bytes
    ) -> Any:
        if path == "/api/health":
            _need(method, "GET")
            return {"status": "ok", "models": len(self.registry.list_models())}

        if path == "/api/models":
            if method == "GET":
                return [ser.model_summary(m) for m in self.registry.list_models()]
            if method == "POST":
                model = ser.model_from_dict(_json_object(body))
                self.registry.register(model)
                return ser.model_to_dict(model)
            raise MethodNotAllowed(f"{method} not allowed on {path}")

        if path.startswith("/api/models/"):
            _need(method, "GET")
            name = unquote(path[len("/api/models/") :])
            return ser.model_to_dict(self.registry.get_model(name))

        if path == "/api/decide":
            _need(method, "POST")
            payload = _json_object(body)
            inputs = payload.get("inputs", {})
            if not isinstance(inputs, dict):
                raise BadRequest("'inputs' must be a JSON object")
            result = self.registry.decide(_require(payload, "model"), inputs)
            return ser.result_to_dict(result)

        if path == "/api/flows/run":
            _need(method, "POST")
            payload = _json_object(body)
            steps = payload.get("steps")
            if not isinstance(steps, list) or not steps:
                raise BadRequest("'steps' must be a non-empty array")
            inputs = payload.get("inputs", {})
            if not isinstance(inputs, dict):
                raise BadRequest("'inputs' must be a JSON object")
            return ser.flow_result_to_dict(self.registry.run_flow(steps, inputs))

        if path == "/api/audit":
            _need(method, "GET")
            model = query.get("model", [None])[0]
            log = self.registry.audit_log
            entries = log.for_model(model) if model else log.entries
            return [ser.audit_entry_to_dict(e) for e in entries]

        raise NotFound(f"no such endpoint: {path}")

    # --- static files -----------------------------------------------------

    def _serve_static(self, method: str, path: str) -> Response:
        _need(method, "GET")
        rel = "index.html" if path == "/" else path.lstrip("/")
        if rel.startswith("static/"):
            rel = rel[len("static/") :]
        base = STATIC_DIR.resolve()
        target = (base / rel).resolve()
        if base not in target.parents or not target.is_file():
            raise NotFound(f"no such file: {path}")
        ctype = _CONTENT_TYPES.get(target.suffix, "application/octet-stream")
        return Response(status=200, body=target.read_bytes(), content_type=ctype)


# --- small request/response helpers --------------------------------------

def _need(method: str, expected: str) -> None:
    if method != expected:
        raise MethodNotAllowed(f"{method} not allowed; use {expected}")


def _json_object(body: bytes) -> dict[str, Any]:
    if not body:
        raise BadRequest("request body is empty")
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise BadRequest(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise BadRequest("request body must be a JSON object")
    return data


def _require(d: Mapping[str, Any], key: str) -> Any:
    if key not in d:
        raise BadRequest(f"missing required field {key!r}")
    return d[key]


def _json(data: Any, status: int = 200) -> Response:
    body = json.dumps(data, default=str).encode("utf-8")
    return Response(status=status, body=body, content_type=_JSON)
