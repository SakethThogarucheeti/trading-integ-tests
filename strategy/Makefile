# Run strategies/ test files as separate pytest invocations (a fresh process
# per file) instead of one combined `pytest strategies/`. Running the full
# suite in one long-lived process accumulates threads/connections/memory
# (testcontainers, ProcessPoolExecutor-based grid searches) to the point
# where later tests run far slower than the same test in isolation -- easy
# to mistake for a hang. See trading-integ-tests#16.
#
# Usage:
#   make test-strategies            # every strategies/test_*.py file, its own process
#   make test-strategies-file FILE=test_backtest.py   # just one file

.PHONY: test-strategies test-strategies-file

STRATEGY_FILES := $(wildcard strategies/test_*.py)

test-strategies:
	@for f in $(STRATEGY_FILES); do \
		echo "=== $$f ==="; \
		uv run pytest "$$f" -q || exit 1; \
	done

test-strategies-file:
	uv run pytest strategies/$(FILE) -q
