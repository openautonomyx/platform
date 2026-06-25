import json

import pytest

from ard.tunnels import LAKEHOUSE_SINKS, seatunnel_job, to_hocon


def test_job_streams_discovery_to_lakehouse():
    job = seatunnel_job("http://registry:8080/", sink="iceberg", table="agentworld.agents")
    assert job["source"][0]["url"] == "http://registry:8080/agents"
    assert job["sink"][0]["plugin_name"] == "Iceberg"
    assert job["sink"][0]["namespace"] == "agentworld"
    assert job["sink"][0]["table"] == "agents"
    assert job["env"]["job.mode"] == "BATCH"


def test_accumulo_secure_sink():
    job = seatunnel_job("http://r", sink="accumulo")
    assert job["sink"][0]["plugin_name"] == "Accumulo"


def test_unknown_sink_rejected():
    with pytest.raises(ValueError):
        seatunnel_job("http://r", sink="nope")
    assert set(LAKEHOUSE_SINKS) == {"iceberg", "paimon", "accumulo"}


def test_hocon_is_parseable_json():
    job = seatunnel_job("http://r")
    assert json.loads(to_hocon(job))["sink"][0]["plugin_name"] == "Iceberg"
