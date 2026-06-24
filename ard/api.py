"""Transport-independent discovery API: ``(method, path, body) -> (status, data)``.

No sockets here, so the whole discovery surface is unit-testable by calling
:meth:`DiscoveryApi.handle` directly. ``ard/server.py`` is the only module that
binds it to ``http.server``.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlsplit

from .card import AgentCard, CardError
from .registry import Registry


class _Http(Exception):
    def __init__(self, status: int, msg: str) -> None:
        self.status = status
        self.msg = msg


def _first(q: dict, key: str) -> str | None:
    vals = q.get(key)
    return vals[0] if vals else None


class DiscoveryApi:
    """Routes discovery requests against a :class:`Registry`."""

    def __init__(self, registry: Registry | None = None) -> None:
        self.registry = registry or Registry()

    def handle(self, method: str, raw_path: str, body: Any = None) -> tuple[int, Any]:
        parts = urlsplit(raw_path)
        path, query = parts.path, parse_qs(parts.query)
        try:
            return self._route(method, path, query, body)
        except _Http as exc:
            return exc.status, {"error": exc.msg}
        except CardError as exc:
            return 400, {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001 — never leak a traceback
            return 500, {"error": f"internal error: {exc}"}

    def _route(self, method: str, path: str, query: dict, body: Any) -> tuple[int, Any]:
        if path == "/healthz":
            return 200, {"status": "ok", "agents": len(self.registry.all())}

        if path == "/agents":
            if method == "GET":
                cards = self.registry.query(
                    skill=_first(query, "skill"),
                    tag=_first(query, "tag"),
                    kind=_first(query, "kind"),
                )
                return 200, [c.to_dict() for c in cards]
            if method == "POST":
                if not isinstance(body, dict):
                    raise _Http(400, "request body must be a JSON object (an agent card)")
                card = self.registry.register(AgentCard.from_dict(body))
                return 201, card.to_dict()
            raise _Http(405, f"{method} not allowed on /agents")

        if path.startswith("/agents/"):
            name = path[len("/agents/"):]
            if method == "DELETE":
                return (204, None) if self.registry.remove(name) else self._missing(name)
            card = self.registry.get(name)
            if card is None:
                return self._missing(name)
            return 200, card.to_dict()

        raise _Http(404, f"no such endpoint: {path}")

    @staticmethod
    def _missing(name: str) -> tuple[int, Any]:
        return 404, {"error": f"no agent named {name!r}"}
