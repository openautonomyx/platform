"""Render Kubernetes manifests for a built agent OCI image.

The pod manager can target a cluster; these are pure functions that render a
Deployment + Service (with discovery annotations + a readiness probe on the
agent-card path) referencing the OCI image produced by ``ard build``.

Output is JSON. JSON is valid YAML, and ``kubectl apply -f`` accepts a
``kind: List`` document — so the JSON these emit applies directly, with no YAML
library dependency.
"""
from __future__ import annotations

import json

from .card import WELL_KNOWN_PATH, AgentCard


def deployment(name: str, image: str, card: AgentCard, port: int = 8080, replicas: int = 1) -> dict:
    labels = {"app": name, "ard.dev/kind": card.kind}
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": name,
            "labels": labels,
            "annotations": {
                "ard.dev/agent": card.name,
                "ard.dev/card-path": WELL_KNOWN_PATH,
            },
        },
        "spec": {
            "replicas": replicas,
            "selector": {"matchLabels": {"app": name}},
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "containers": [
                        {
                            "name": name,
                            "image": image,
                            "ports": [{"containerPort": port}],
                            "readinessProbe": {
                                "httpGet": {"path": WELL_KNOWN_PATH, "port": port},
                                "initialDelaySeconds": 2,
                                "periodSeconds": 10,
                            },
                        }
                    ]
                },
            },
        },
    }


def service(name: str, port: int = 8080) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": name, "labels": {"app": name}},
        "spec": {
            "selector": {"app": name},
            "ports": [{"port": port, "targetPort": port}],
        },
    }


def manifests(name: str, image: str, card: AgentCard, port: int = 8080, replicas: int = 1) -> list[dict]:
    return [deployment(name, image, card, port, replicas), service(name, port)]


def manifest_list(name: str, image: str, card: AgentCard, port: int = 8080, replicas: int = 1) -> dict:
    """A single ``kind: List`` document, ready for ``kubectl apply -f``."""
    return {"apiVersion": "v1", "kind": "List", "items": manifests(name, image, card, port, replicas)}


def to_json(name: str, image: str, card: AgentCard, port: int = 8080, replicas: int = 1) -> str:
    return json.dumps(manifest_list(name, image, card, port, replicas), indent=2)
