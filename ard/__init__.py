"""ard — an ecosystem framework that makes agents discoverable.

The loop: **build → deploy → register → discover.**

- **build**  — Cloud Native Buildpacks bake an agent into an OCI image ("the box"
  ships the buildpacks; the build runs at the user's desk against their env).
- **deploy** — the pod manager runs the image as a *tool server* or *skill server*.
- **register / discover** — every server publishes an A2A *agent card*; the
  registry indexes them and answers discovery queries.

This package is the Python core + CLI. The CNB buildpacks live under
``buildpacks/`` and ship as a builder image.
"""
from .api import DiscoveryApi
from .builder import BuildResult, build_image, pack_available
from .card import AgentCard, AgentSkill, CardError, WELL_KNOWN_PATH
from .detect import EnvContext, detect
from .pod import FakeRuntime, LocalDockerRuntime, ManifestRuntime, Pod, PodManager, PodSpec
from .registry import Registry
from .sdk import agent_card, discoverable

__version__ = "0.1.0"

__all__ = [
    "AgentCard", "AgentSkill", "CardError", "WELL_KNOWN_PATH",
    "EnvContext", "detect",
    "Registry", "DiscoveryApi",
    "Pod", "PodSpec", "PodManager", "ManifestRuntime", "LocalDockerRuntime", "FakeRuntime",
    "BuildResult", "build_image", "pack_available",
    "agent_card", "discoverable",
    "__version__",
]
