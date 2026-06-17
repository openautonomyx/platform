"""Decision monitoring & governance.

Implements the DIP *Decision monitoring* and *Decision governance* mandatory
features: log and audit every decision so it can be reviewed, traced and
governed as an asset.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, TYPE_CHECKING

if TYPE_CHECKING:  # avoid a runtime import cycle with engine
    from .engine import DecisionResult


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class AuditEntry:
    """An immutable record of a single executed decision."""

    timestamp: datetime
    model: str
    inputs: dict[str, Any]
    outcome: Any
    matched_rule: str | None


class AuditLog:
    """An append-only log of decisions for monitoring and governance.

    A ``clock`` may be injected for deterministic timestamps in tests.
    """

    def __init__(self, clock: Callable[[], datetime] = _utcnow) -> None:
        self._clock = clock
        self._entries: list[AuditEntry] = []

    def record(self, result: "DecisionResult") -> AuditEntry:
        """Append an audit entry derived from a decision result."""
        entry = AuditEntry(
            timestamp=self._clock(),
            model=result.model,
            inputs=dict(result.inputs),
            outcome=result.outcome,
            matched_rule=result.matched_rule,
        )
        self._entries.append(entry)
        return entry

    @property
    def entries(self) -> tuple[AuditEntry, ...]:
        """All recorded entries in insertion order."""
        return tuple(self._entries)

    def for_model(self, name: str) -> tuple[AuditEntry, ...]:
        """Entries recorded for a particular model name."""
        return tuple(e for e in self._entries if e.model == name)

    def filter(self, predicate: Callable[[AuditEntry], bool]) -> tuple[AuditEntry, ...]:
        """Entries matching an arbitrary predicate."""
        return tuple(e for e in self._entries if predicate(e))

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self) -> Iterable[AuditEntry]:
        return iter(self._entries)
