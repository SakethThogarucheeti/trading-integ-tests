# trading-integ-tests

Integration tests for the `trading-platform` engine. Split out of `trading-platform/tst/integ/`
into its own repo since these suites carry their own heavy dependencies (testcontainers,
scikit-learn, plotly) and Docker requirement, separate from the fast unit tests that still
live in `trading-platform/tst/unit/`.

Two suites, each with its own Python environment and `pyproject.toml`. Both require Docker to
spin up Postgres. Both depend on `trading-platform` via an
editable path dependency (`../../trading-platform`), so local changes to the engine are
picked up without reinstalling.

## Suites

| Directory | What it tests | Run from |
|-----------|--------------|---------|
| `strategy/` | Indicators, backtests, walk-forward, Monte Carlo, hyperparameter search | `strategy/` |
| `system/` | Full end-to-end pipeline: tick → signal → order → position | `system/` |

## Quick start

```bash
# Strategy tests
cd strategy && uv sync && uv run pytest .

# System tests
cd system && uv sync && uv run pytest .
```

## Conventions

- Each suite has a single `conftest.py` that provides `pg_container` (session-scoped Postgres via testcontainers) and per-test fixtures.
- All tables are truncated after each test — tests are isolated and can run in any order.
- Tests in `strategy/` use the `testing/` library for backtesting harness, Monte Carlo engine, and walk-forward splits.
