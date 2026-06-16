# `dip` — a minimal Decision Intelligence Platform engine

A small, dependency-free Python implementation of the core capabilities a
Decision Intelligence Platform (DIP) provides, modelled on the mandatory
features listed in this repo's [`features`](../features) file.

| DIP feature (from `features`)   | Where it lives            |
| ------------------------------- | ------------------------- |
| Decision modeling               | `dip/model.py`            |
| Decision execution              | `dip/engine.py`           |
| Decision service composition    | `dip/composition.py`      |
| Decision monitoring & governance| `dip/governance.py`       |

## Concepts

- **`Condition`** — a single comparison of an input field (`Operator.GTE`, `EQ`, `IN`, …).
- **`Rule`** — named conditions combined with `Logic.ALL`/`ANY`, producing an outcome; carries a `priority`.
- **`DecisionModel`** — prioritised rules + a default outcome and (optional) declared inputs.
- **`DecisionEngine`** — executes a model against data; first matching rule (by priority) wins. Returns a `DecisionResult` with an explainable `trace`.
- **`AuditLog`** — append-only record of every decision, for monitoring/governance.
- **`DecisionService` / `DecisionFlow`** — wrap models as reusable components and orchestrate them in sequence.

## Example

```python
from dip import (
    Condition, DecisionEngine, DecisionModel, Operator, Rule, AuditLog,
)

model = DecisionModel(
    name="credit",
    inputs=("score", "amount"),
    default_outcome="manual_review",
    rules=[
        Rule("auto-decline", (Condition("score", Operator.LT, 500),),
             outcome="decline", priority=20),
        Rule("auto-approve",
             (Condition("score", Operator.GTE, 700),
              Condition("amount", Operator.LTE, 10_000)),
             outcome="approve", priority=10),
    ],
)

log = AuditLog()
engine = DecisionEngine(audit_log=log)

result = engine.execute(model, {"score": 750, "amount": 5_000})
print(result.outcome)        # "approve"
print(result.matched_rule)   # "auto-approve"
print(len(log))              # 1
```

## Running the tests

```bash
pip install pytest
pytest
```
