# ard — make every agent discoverable

`ard` is the **build → deploy → discover** layer of the AgentWorld ecosystem.
It ships as a **box** (a [Cloud Native Buildpacks](https://buildpacks.io) builder)
you hand to a developer; at their desk it **detects their environment**, **builds**
their agent into an **OCI image**, the **pod manager** runs it as a *tool server*
or *skill server*, and every server publishes an **[A2A](https://a2a-protocol.org)
agent card** at `/.well-known/agent.json` so the **registry** can discover it.

> Dependency-free Python core + CLI (standard library only). The buildpacks are
> standard CNB and run via `pack`.

## Where it sits (openagx)

| Repo | Role |
| --- | --- |
| `openagx/Platform` | Agentic autonomous **governance** platform |
| `openagx/services` · `openagx/Skills` | the **tool/skill servers** ard builds & deploys |
| `openagx/AuthX-ID` | agent **identity** (cards can carry its auth schemes) |
| **`ard`** | **build → deploy → discover** — the glue between them |

## The loop

```
ard detect ./my-agent                         # which buildpack claims it
ard build  ./my-agent --image ghcr.io/acme/agent:0.1   # CNB → OCI ("the box")
ard deploy --image ghcr.io/acme/agent:0.1 --card card.json   # run as a pod
ard serve                                      # the discovery registry
ard discover --skill refund --kind tool        # find agents by capability
```

Becoming discoverable from code is a couple of lines:

```python
from ard import discoverable

@discoverable(name="billing", kind="tool", skills=["refund", "invoice.lookup"])
class BillingAgent: ...
```

## The box (Cloud Native Buildpacks)

```bash
# build the box (your desk / CI), then build any agent with it
pack builder create ard/box --config builder.toml
pack build ghcr.io/acme/agent:0.1 --builder ard/box --path ./my-agent
```

`buildpacks/ard-python` and `buildpacks/ard-node` each `detect` their stack and,
in `build`, install deps, emit the agent's A2A card, and set the web process.
`builder.toml` assembles them into the box.

## Architecture

| Module | Responsibility |
| --- | --- |
| `ard/card.py` | A2A agent card — the universal descriptor (+ `x-ard` kind) |
| `ard/detect.py` | environment detection (the read side of build-at-desk) |
| `ard/builder.py` | drives the CNB lifecycle (`pack`) to bake the OCI image |
| `ard/pod.py` | pod manager — deploy/track tool & skill servers (local / manifest runtimes) |
| `ard/k8s.py` | render Deployment + Service for a built image |
| `ard/registry.py` · `ard/api.py` · `ard/server.py` | the discovery hub |
| `ard/sdk.py` | `@discoverable` — the per-agent adoption surface |
| `buildpacks/` · `builder.toml` | the CNB buildpacks and the box |

## Run / test

```bash
pip install -e .        # provides the `ard` CLI
pip install pytest && pytest    # 26 tests
```

## MVP scope (honest)

- **Building the OCI image** needs `pack` + a container runtime at the user's
  desk; without them `ard build` prints the exact plan (`--dry-run`).
- The pod manager ships a **local Docker runtime** and a **K8s manifest**
  runtime (emits `kubectl apply`-ready JSON); wiring a live cluster client is
  the next step.
- Agent cards follow the A2A shape; `securitySchemes` / AuthX-ID integration is
  stubbed for now.
