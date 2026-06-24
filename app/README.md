# `app` — Decision Intelligence Console

A small, dependency-free web application on top of the [`dip`](../dip) engine.
It turns the engine's library API into an interactive **decision intelligence
console**: a JSON HTTP API plus a single-page browser UI for modelling,
executing, orchestrating and governing decisions.

Like `dip`, it uses **only the Python standard library** — no install step, no
third-party packages.

## Run it

```bash
python -m app                 # serves http://127.0.0.1:8000
python -m app --port 9000     # custom port
```

Then open the printed URL in a browser.

## What it exposes

The UI is organised around the DIP mandatory features (see the repo's
[`features`](../features) file), with an orchestration + governance framing that
mirrors the broader Business Orchestration and Automation Technologies (BOAT)
pattern — coordinate decision services and keep an auditable record of every step.

| Tab          | DIP feature                     | API endpoint(s)                       |
| ------------ | ------------------------------- | ------------------------------------- |
| Models       | Decision modeling               | `GET/POST /api/models`, `GET /api/models/{name}` |
| Decide       | Decision execution              | `POST /api/decide`                    |
| Orchestrate  | Decision service composition    | `POST /api/flows/run`                 |
| Governance   | Decision monitoring & governance| `GET /api/audit`                      |

Three example models are seeded on startup (`credit`, and a `risk` → `routing`
pair designed to be chained as a flow).

## API quick reference

```bash
# Run a decision and get an explainable trace
curl -s localhost:8000/api/decide \
  -d '{"model": "credit", "inputs": {"score": 750, "amount": 5000}}'
# → {"outcome": "approve", "matched_rule": "auto-approve", "matched": true, "trace": [...]}

# Orchestrate a flow (each step's outcome feeds the next via a mapper)
curl -s localhost:8000/api/flows/run \
  -d '{"steps": [{"service": "risk"},
                 {"service": "routing", "mapper": {"risk": "risk_outcome"}}],
       "inputs": {"amount": 50000}}'
# → {"results": {...}, "final_outcome": "human"}

# Inspect the governance audit log
curl -s localhost:8000/api/audit
```

A model posted to `POST /api/models` is JSON shaped like:

```json
{
  "name": "credit",
  "inputs": ["score", "amount"],
  "default_outcome": "manual_review",
  "rules": [
    {"name": "auto-decline", "priority": 20,
     "conditions": [{"field": "score", "operator": "lt", "value": 500}],
     "outcome": "decline"}
  ]
}
```

Operators: `eq, ne, gt, gte, lt, lte, in, not_in, contains`. Rule `logic` is
`all` (AND, default) or `any` (OR).

## Layout

| File                | Responsibility                                            |
| ------------------- | --------------------------------------------------------- |
| `api.py`            | Transport-independent router: `(method, path, body)` → `Response` |
| `server.py`         | stdlib `http.server` wiring (the only module that knows about sockets) |
| `registry.py`       | In-memory models + shared audit log + seeded examples     |
| `serialization.py`  | `dip` dataclasses ⇄ JSON                                  |
| `errors.py`         | HTTP-aware error types                                    |
| `static/`           | Single-page UI (`index.html`, `style.css`, `app.js`)      |

Because `api.py` has no socket dependency, the entire API is unit-tested by
calling `Api.handle(...)` directly — see [`tests/test_app_api.py`](../tests/test_app_api.py).

## Tests

```bash
pip install pytest
pytest
```
