"""Pod manager — deploy built agent OCI images as tool/skill servers, track them.

A *pod* is an instance of a built agent image. The manager is runtime-pluggable:

  - :class:`ManifestRuntime` (default) — render K8s manifests; no live cluster.
  - :class:`LocalDockerRuntime` — ``docker run`` the OCI image at the user's desk.
  - :class:`FakeRuntime` — in-memory, for tests.

On deploy, the pod's agent card is pushed to the discovery registry, so a
deployed server is immediately discoverable. Pod state persists to JSON so
``ard pods`` reflects reality across CLI invocations.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from dataclasses import dataclass, field

from . import k8s
from .card import AgentCard
from .registry import Registry


@dataclass
class PodSpec:
    name: str
    image: str  # OCI image ref produced by `ard build`
    card: AgentCard
    kind: str = "skill"
    port: int = 8080
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class Pod:
    name: str
    image: str
    kind: str
    port: int
    status: str = "pending"  # pending | running | stopped | failed
    handle: str | None = None  # container id / manifest marker
    url: str | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "image": self.image,
            "kind": self.kind,
            "port": self.port,
            "status": self.status,
            "handle": self.handle,
            "url": self.url,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Pod":
        return cls(**{k: d.get(k) for k in ("name", "image", "kind", "port", "status", "handle", "url")})


# --- runtimes -------------------------------------------------------------


class ManifestRuntime:
    """'Deploys' by rendering manifests — no live cluster required."""

    name = "manifest"

    def start(self, spec: PodSpec) -> str:
        return "manifest"

    def stop(self, pod: Pod) -> bool:
        return True

    def is_alive(self, pod: Pod) -> bool:
        return pod.status == "running"


class FakeRuntime:
    """In-memory runtime for tests."""

    name = "fake"

    def __init__(self) -> None:
        self.started: list[str] = []
        self.stopped: list[str] = []

    def start(self, spec: PodSpec) -> str:
        self.started.append(spec.name)
        return f"fake-{spec.name}"

    def stop(self, pod: Pod) -> bool:
        self.stopped.append(pod.name)
        return True

    def is_alive(self, pod: Pod) -> bool:
        return pod.name not in self.stopped


class LocalDockerRuntime:
    """Runs the OCI image locally via ``docker run`` (build-at-desk smoke test)."""

    name = "docker"

    def start(self, spec: PodSpec) -> str:
        if not shutil.which("docker"):
            raise RuntimeError("docker not found on PATH")
        cmd = ["docker", "run", "-d", "-p", f"{spec.port}:{spec.port}"]
        for k, v in spec.env.items():
            cmd += ["-e", f"{k}={v}"]
        cmd.append(spec.image)
        return subprocess.check_output(cmd, text=True).strip()

    def stop(self, pod: Pod) -> bool:
        if pod.handle:
            subprocess.run(["docker", "rm", "-f", pod.handle], check=False)
        return True

    def is_alive(self, pod: Pod) -> bool:
        if not pod.handle:
            return False
        out = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", pod.handle],
            capture_output=True, text=True, check=False,
        )
        return out.stdout.strip() == "true"


# --- manager --------------------------------------------------------------


class PodManager:
    def __init__(self, runtime=None, state_path: str | None = None, registry: Registry | None = None) -> None:
        self.runtime = runtime or ManifestRuntime()
        self.state_path = state_path
        self.registry = registry
        self._pods: dict[str, Pod] = {}
        self._lock = threading.Lock()
        if state_path and os.path.exists(state_path):
            self._load()

    def deploy(self, spec: PodSpec) -> Pod:
        spec.card.validate()
        try:
            handle = self.runtime.start(spec)
            status = "running"
        except Exception:
            handle, status = None, "failed"
        pod = Pod(
            name=spec.name, image=spec.image, kind=spec.kind, port=spec.port,
            status=status, handle=handle, url=f"http://localhost:{spec.port}",
        )
        with self._lock:
            self._pods[spec.name] = pod
            self._save()
        if status == "running" and self.registry is not None:
            self.registry.register(spec.card)  # deployed → discoverable
        return pod

    def manifests(self, spec: PodSpec) -> dict:
        return k8s.manifest_list(spec.name, spec.image, spec.card, spec.port)

    def list(self) -> list[Pod]:
        with self._lock:
            return list(self._pods.values())

    def status(self, name: str) -> Pod | None:
        pod = self._pods.get(name)
        if pod and pod.status == "running" and not self.runtime.is_alive(pod):
            pod.status = "stopped"
            self._save()
        return pod

    def stop(self, name: str) -> bool:
        with self._lock:
            pod = self._pods.get(name)
            if not pod:
                return False
            self.runtime.stop(pod)
            pod.status = "stopped"
            self._save()
            return True

    # --- persistence ------------------------------------------------------

    def _save(self) -> None:
        if not self.state_path:
            return
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump([p.to_dict() for p in self._pods.values()], f, indent=2)

    def _load(self) -> None:
        with open(self.state_path, encoding="utf-8") as f:
            for d in json.load(f):
                pod = Pod.from_dict(d)
                self._pods[pod.name] = pod
