"""Tunnels — move ard's discovery & governance data into a lakehouse.

A *tunnel* is a data-integration job, run by **Apache SeaTunnel** at the data
plane, that streams ard's agent registry / governance feed into a **lakehouse**
table (Apache Iceberg / Apache Paimon) or a secure store (**Apache Accumulo** —
cell-level security that pairs with AuthX-ID identities).

ard *generates* the job spec; SeaTunnel *executes* it. These are pure functions
(→ unit-testable); running the job needs a SeaTunnel cluster + the sink.
"""
from __future__ import annotations

import json

# SeaTunnel sink connector per target. Accumulo = secure cell-level store.
LAKEHOUSE_SINKS = {
    "iceberg": "Iceberg",
    "paimon": "Paimon",
    "accumulo": "Accumulo",
}


def seatunnel_job(
    source_url: str,
    sink: str = "iceberg",
    table: str = "agentworld.agents",
    warehouse: str = "s3://agentworld/lakehouse",
) -> dict:
    """A SeaTunnel job: ard discovery feed (HTTP ``/agents``) → lakehouse table."""
    connector = LAKEHOUSE_SINKS.get(sink)
    if connector is None:
        raise ValueError(f"unknown sink {sink!r}; choose from {sorted(LAKEHOUSE_SINKS)}")
    namespace, _, tbl = table.rpartition(".")
    return {
        "env": {"parallelism": 1, "job.mode": "BATCH"},
        "source": [
            {
                "plugin_name": "Http",
                "url": source_url.rstrip("/") + "/agents",
                "format": "json",
                "result_table_name": "ard_agents",
            }
        ],
        "transform": [
            {
                "plugin_name": "Sql",
                "source_table_name": "ard_agents",
                "result_table_name": "ard_agents_flat",
                "query": "select name, version, url, `x-ard`.kind as kind from ard_agents",
            }
        ],
        "sink": [
            {
                "plugin_name": connector,
                "source_table_name": "ard_agents_flat",
                "warehouse": warehouse,
                "namespace": namespace or "agentworld",
                "table": tbl,
            }
        ],
    }


def to_hocon(job: dict) -> str:
    """Render a SeaTunnel job as text. SeaTunnel accepts JSON (a HOCON subset)."""
    return json.dumps(job, indent=2)
