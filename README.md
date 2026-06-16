# MetaKube

**A Kubernetes-native Decision Intelligence Platform.**

MetaKube is a backend service + REST API for building *decision-centric*
solutions: model decisions declaratively, execute them at scale, monitor
decision quality, keep humans in the loop, compose reusable decision services,
and govern everything with an immutable audit trail and policies.

It is written in Go using **only the standard library** (no third-party
dependencies), so it builds offline, starts in milliseconds, and ships as a
single ~9 MB static binary in a non-root distroless container.

> Decision intelligence platforms create decision-centric solutions that
> support, augment and automate decisions of humans or machines, powered by the
> composition of data, analytics, knowledge and AI. — *Gartner*

---

## The six DIP capabilities, and how MetaKube implements each

| Capability | What it means | In MetaKube |
|---|---|---|
| **Decision modeling** | Design explainable decision models with defined inputs, flow and outputs | Declarative JSON models: inputs → derivations → knockouts → scorecard → decision table. `POST /v1/models` |
| **Decision execution** | Orchestrate and execute decision flows, batch and real-time | A compiled engine evaluates models into an outcome + trace. `POST /v1/models/{id}/execute`, `…/simulate` |
| **Decision service composition** | Componentize decisions as modular, discoverable, reusable services | Every model is a versioned service with a published I/O schema and endpoint. `GET /v1/services` |
| **Decision monitoring** | See each decision, its logic and metadata; track quality | Full per-run trace plus aggregated quality metrics. `GET /v1/runs`, `GET /v1/runs/{id}`, `GET /v1/metrics` |
| **Decision collaboration** | Human-AI delegation with guardrails and thresholds | Borderline outcomes are routed to a review queue; humans resolve them, overrides are recorded. `GET /v1/reviews`, `…/resolve` |
| **Decision governance** | Log, audit and govern decisions as assets with policies | Append-only audit log + policies that actually override decisions. `GET /v1/audit`, `GET/PUT /v1/policies` |

---

## Quickstart

```bash
# Run locally (defaults to :8080)
make run            # or: go run ./cmd/metakube

# In another terminal — execute a loan decision:
curl -s localhost:8080/v1/models/loan-approval/execute \
  -H 'content-type: application/json' \
  -d '{"inputs":{
        "creditScore":742,"annualIncome":96000,"monthlyDebt":1600,
        "loanAmount":28000,"employmentYears":5,"age":38,
        "loanPurpose":"auto","priorDefaults":0}}' | jq .outcome
```

```jsonc
{
  "decision": "APPROVE",
  "riskScore": 79,
  "tier": "A",
  "confidence": 0.85,
  "reasonCodes": [
    { "code": "TIER_A", "description": "Strong risk profile" },
    { "code": "CREDIT_VERY_GOOD", "description": "Very good credit score (700-759)", "impact": 20 }
  ],
  "explanation": "Approved with a risk score of 79. Primary drivers: ..."
}
```

Populate the dashboards and review queue with synthetic traffic, then inspect:

```bash
curl -s localhost:8080/v1/models/loan-approval/simulate -d '{"count":500,"seed":42}'
curl -s localhost:8080/v1/metrics | jq
curl -s localhost:8080/v1/reviews | jq '.count'
```

End-to-end smoke test:

```bash
make smoke          # boots the server and exercises every endpoint
```

---

## Anatomy of a decision model

Models are plain JSON. Rules are written in a small, safe expression language
(`creditScore >= 700 && dti <= 0.35`) that supports arithmetic, comparison,
equality, short-circuit logic, dotted identifiers and the builtins
`min/max/abs/round/floor/ceil`. A model is a pipeline:

1. **Inputs** — typed and validated (`number` / `string` / `boolean`, with
   `min`/`max`/`enum`/`required`).
2. **Derivations** — intermediate values, e.g. `dti = monthlyDebt / monthlyIncome`.
3. **Knockouts** — hard rules; any that fire force a `DECLINE`.
4. **Scorecard** — weighted factors accumulate a bounded risk score.
5. **Decision table** — first matching row yields `APPROVE` / `REVIEW` / `DECLINE`.

Every evaluation returns a **trace** (each stage, which rules fired, the final
context) so decisions are fully explainable and auditable.

Register your own model:

```bash
curl -s -X POST localhost:8080/v1/models -H 'content-type: application/json' -d @my-model.json
```

---

## API reference

See [`api/openapi.yaml`](api/openapi.yaml) for the full OpenAPI 3 spec.

| Method & path | Purpose |
|---|---|
| `GET /healthz`, `GET /readyz` | Liveness / readiness probes |
| `GET /version`, `GET /metrics` | Build info / Prometheus metrics |
| `GET /v1/models`, `POST /v1/models` | List / register models |
| `GET /v1/models/{id}`, `…/versions` | Model definition / version history |
| `GET /v1/services` | Discover composable decision services |
| `POST /v1/models/{id}/execute` | Execute a decision |
| `POST /v1/models/{id}/simulate` | Generate synthetic traffic |
| `GET /v1/runs`, `GET /v1/runs/{id}` | Decision history / single run + trace |
| `GET /v1/metrics` | Aggregated decision-quality metrics |
| `GET /v1/reviews`, `POST /v1/reviews/{id}/resolve` | Human-in-the-loop queue |
| `GET /v1/audit` | Immutable audit log |
| `GET /v1/policies`, `PUT /v1/policies/{id}` | Governance policies |

---

## Container & Kubernetes

```bash
# Build the image (multi-stage, distroless, non-root)
make docker-build           # IMAGE=metakube:latest

# Run it
docker run --rm -p 8080:8080 metakube:latest
```

Deploy to Kubernetes (manifests in [`deploy/k8s`](deploy/k8s) — Deployment with
liveness/readiness/startup probes, resource limits, a hardened
`securityContext`, HPA and PodDisruptionBudget):

```bash
# minikube example
minikube start
eval "$(minikube docker-env)"        # build straight into minikube's daemon
make docker-build
make k8s-deploy                      # kubectl apply -k deploy/k8s
kubectl -n metakube port-forward svc/metakube 8080:80
```

---

## Cloud deployment

Run the real Go service on **Fly.io**, **Render** or **Google Cloud Run** — see
**[DEPLOY.md](DEPLOY.md)**. Each builds the repo `Dockerfile` and gives a public
HTTPS URL with custom-domain support.

## Configuration

All configuration is via environment variables (12-factor):

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8080` | Listen port |
| `METAKUBE_ADDR` | `:8080` | Full listen address (overrides `PORT`) |
| `LOG_LEVEL` | `info` | `debug` / `info` / `warn` / `error` |
| `READ_TIMEOUT_SECONDS` | `10` | HTTP read timeout |
| `WRITE_TIMEOUT_SECONDS` | `30` | HTTP write timeout |
| `IDLE_TIMEOUT_SECONDS` | `120` | HTTP idle timeout |
| `SHUTDOWN_TIMEOUT_SECONDS` | `15` | Graceful drain timeout |
| `METAKUBE_ACCESS` | `open` | `open` (no auth) or `enforce` (role-based access) |
| `METAKUBE_ROOT_AGENT` | `root` | Bootstrap author identity seeded at startup |

---

## Agents, tools & access control

Agents are first-class, durable identities. Callers identify with an `X-Agent`
header (falling back to `X-Actor`); every decision, audit entry and access-log
line is attributed to that agent, and agents accrue activity history.

- **Registry** — `GET/POST /v1/agents`, `GET /v1/agents/{id}`: register agents
  with roles; request counts and first/last-seen are tracked automatically.
- **Tools** — `GET /v1/tools` exposes each decision service as a function-calling
  tool spec (JSON-Schema params + invoke), so AI agents can discover and call
  decisions directly.
- **Access control (opt-in)** — set `METAKUBE_ACCESS=enforce` to require roles:

  | Caller | May |
  |---|---|
  | `author` role (or `*`) | Everything — create/replace models, update policies, register agents, resolve reviews |
  | any identified agent | Execute decisions and read catalog/services/metrics (consumer) |
  | anonymous | Public ops endpoints only |

  Default is `open` (no enforcement), so existing clients are unaffected. A
  bootstrap author (`METAKUBE_ROOT_AGENT`, default `root`, role `*`) is seeded at
  startup so enforce mode is usable immediately.

## Stability & operations

MetaKube is built to be boring and reliable in production:

- **No third-party dependencies** — nothing to break, audit or chase CVEs in.
- **Graceful shutdown** — handles `SIGTERM`, drains in-flight requests and fails
  readiness first, so rolling updates don't drop traffic.
- **Panic recovery** — a bad request can never take down the server.
- **Request timeouts & body limits** — protects against slow-loris and oversized
  payloads.
- **Bounded memory** — runs history and audit log are ring-buffered.
- **Concurrency-safe** — all shared state is guarded; run with `go test -race`.
- **Hardened container** — non-root, read-only root filesystem, all capabilities
  dropped, `RuntimeDefault` seccomp.
- **Observability** — structured JSON access logs with request IDs and a
  Prometheus endpoint.

---

## Project layout

```
cmd/metakube/        entrypoint: config, wiring, graceful shutdown
internal/expr/       safe expression language (lexer, parser, evaluator)
internal/engine/     model types + compile/evaluate with explainability trace
internal/catalog/    concurrency-safe model registry + seed services
internal/store/      runs, audit log, review queue, governance policies
internal/api/        HTTP server, routing, middleware, handlers, metrics
internal/version/    build metadata (ldflags-injected)
api/openapi.yaml     OpenAPI 3 specification
deploy/k8s/          Kubernetes manifests (kustomize)
```

## Testing

```bash
make test           # go test ./... -race
make cover          # coverage summary
make vet fmt-check  # static checks
```
