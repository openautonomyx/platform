"""ard (Agent Discovery) — an ecosystem framework that makes agents discoverable.

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
from .bridges import GovernanceSink, JsonlSink, NullSink, to_catalog_entry
from .builder import BuildResult, build_image, pack_available
from .card import AgentCard, AgentSkill, CardError, WELL_KNOWN_PATH
from .detect import EnvContext, detect
from .federation import Federation, Peer
from .handoff import HANDOFF_VERSION, HandoffBroker, HandoffError, HandoffReceipt, HandoffRequest
from .identity import AuthXIdentity, authx_scheme, check_identity, require_authx, secure_with_authx
from .pod import FakeRuntime, LocalDockerRuntime, ManifestRuntime, Pod, PodManager, PodSpec
from .registry import Registry
from .sdk import agent_card, discoverable
from .trust import TrustScore, score_card
from .tunnels import LAKEHOUSE_SINKS, seatunnel_job, to_hocon

__version__ = "0.3.0"

__all__ = [
    "AgentCard", "AgentSkill", "CardError", "WELL_KNOWN_PATH",
    "EnvContext", "detect",
    "AuthXIdentity", "authx_scheme", "require_authx", "secure_with_authx", "check_identity",
    "Registry", "DiscoveryApi", "Federation", "Peer",
    "Pod", "PodSpec", "PodManager", "ManifestRuntime", "LocalDockerRuntime", "FakeRuntime",
    "BuildResult", "build_image", "pack_available",
    "GovernanceSink", "NullSink", "JsonlSink", "to_catalog_entry",
    "LAKEHOUSE_SINKS", "seatunnel_job", "to_hocon",
    "HandoffBroker", "HandoffRequest", "HandoffReceipt", "HandoffError", "HANDOFF_VERSION",
    "TrustScore", "score_card",
    "agent_card", "discoverable",
    "__version__",
]
