"""A small web application on top of the :mod:`dip` decision engine.

The *Decision Intelligence Console* exposes the engine's mandatory DIP
capabilities over a JSON HTTP API and a single-page browser UI:

* **Decision modeling** — define and inspect models (``/api/models``).
* **Decision execution** — run a model and get an explainable trace (``/api/decide``).
* **Decision service composition** — orchestrate models as a flow (``/api/flows/run``).
* **Decision monitoring & governance** — every decision is recorded to a shared
  audit log (``/api/audit``).

The orchestration + governance framing mirrors the broader Business
Orchestration and Automation Technologies (BOAT) pattern: coordinate decision
services and keep an auditable record of every step.
"""
from __future__ import annotations

from .api import Api, Response
from .registry import Registry
from .server import serve

__all__ = ["Api", "Response", "Registry", "serve"]

__version__ = "0.1.0"
