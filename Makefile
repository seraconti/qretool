# No src/ layout yet - that is SPEC 0002. `core` is the layering root AGENTS.md
# section 3 names, so it is what the type gate checks today. Becomes src/quebra/core
# when the tree moves.
PKG := core
FAST := -m "not slow and not heavy and not real and not r"

.PHONY: check lint types arch deps test test-all test-r docs clean

## Run before every checkpoint. This is what the checkpoint banner reports.
check: lint types arch test

lint:
	ruff check .
	ruff format --check .

## Phase 1 onward: mypy needs the src layout to exist first.
types:
	@command -v mypy >/dev/null 2>&1 || { echo "SKIPPED types: mypy not installed; needs the src/ layout (SPEC 0002)"; exit 0; }; \
	mypy $(PKG)

## Phase 2 onward: needs the import-linter contract in pyproject.toml.
arch:
	@command -v lint-imports >/dev/null 2>&1 || { echo "SKIPPED arch: lint-imports not installed; needs the import-linter contract in pyproject.toml (SPEC 0002)"; exit 0; }; \
	lint-imports

deps:
	@command -v deptry >/dev/null 2>&1 || { echo "SKIPPED deps: deptry not installed; needs pyproject.toml (SPEC 0002)"; exit 0; }; \
	deptry .

## What CI runs on every push, and what a JOSS reviewer will run.
## Must pass with zero private data and zero R.
test:
	pytest $(FAST)

## Everything a laptop can run without private data.
test-all:
	pytest -m "not real"

## Separate CI job. Requires Rscript plus copula and randtests.
test-r:
	pytest -m "r"

## Local only. Touches data/real_private/. Never on GitHub Actions.
test-real:
	pytest -m "real or regression"

## Phase 8 onward.
docs:
	sphinx-build -W --nitpicky -b html docs docs/_build/html

clean:
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
