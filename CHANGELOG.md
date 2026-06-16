# Changelog

All notable changes to MetaKube are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com), and the project follows
[Semantic Versioning](https://semver.org).

## [0.1.0] - 2026-06-16

Initial release of **MetaKube** — a Kubernetes-native Decision Intelligence
Platform implemented in Go using only the standard library (no third-party
dependencies).

### Decision intelligence (the six DIP capabilities)
- **Modeling** — declarative JSON models (inputs, derivations, knockouts,
  scorecard, decision table) with a safe, dependency-free expression language.
- **Execution** — compiled engine producing an outcome plus a full
  explainability trace; single execution and bulk simulation.
- **Service composition** — models exposed as versioned, discoverable decision
  services with published I/O schemas.
- **Monitoring** — per-run history and traces, aggregated decision-quality
  metrics, and a Prometheus endpoint.
- **Collaboration** — human-in-the-loop review queue with override tracking.
- **Governance** — append-only audit log and policies that can override
  decisions.

### Agentic layer
- Agent-identity middleware (`X-Agent`/`X-Actor`) attributing every decision,
  action and log line.
- Durable agent registry with roles and activity tracking.
- Agent-callable tools: decision services exposed as function-calling specs
  (`GET /v1/tools`).
- Opt-in role-based access control (author vs consumer), enforced via
  `METAKUBE_ACCESS`.

### Authoring
- Model dry-run/validate (compile + evaluate without registering) and delete.

### Data fabric
- Pluggable external-signal connector framework with a config-gated Facebook
  Graph connector (OAuth authorization URL, fine-grained scopes, comment fetch).

### Operations
- Multi-stage non-root distroless container; Kubernetes manifests (Deployment
  with probes/limits/hardened `securityContext`, Service, HPA, PDB); cloud
  configs for Fly.io, Render and Cloud Run.
- Graceful `SIGTERM` shutdown, request timeouts and body limits, panic recovery,
  structured JSON logging, health/readiness probes.
- OpenAPI 3 spec, Makefile, smoke script, and GitHub Actions CI (gofmt, vet,
  race tests, build, docker build).

[0.1.0]: https://github.com/openautonomyx/platform/releases/tag/v0.1.0
