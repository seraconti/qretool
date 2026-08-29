# The src/ layout landed in SPEC 0002. mypy checks the layering root AGENTS.md section 3
# names; widening it to the whole package is a later phase with its own checkpoint.
PKG := src/quebra/core
# deptry scans the DISTRIBUTED package only. `jobs/` legitimately imports joblib and
# quebra, and neither is a dependency of the wheel - that is the point of D1.
PKGROOT := src/quebra
FAST := -m "not slow and not heavy and not real and not r"

.PHONY: check lint types arch deps test test-all test-r test-real promote docs clean

## Run before every checkpoint. This is what the checkpoint banner reports.
check: lint types arch test

lint:
	ruff check .
	ruff format --check .

## Phase 1 onward: mypy needs the src layout to exist first.
types:
	mypy $(PKG)

## Phase 2 onward: needs the import-linter contract in pyproject.toml.
arch:
	@python3 -c "import tomllib,sys; d=tomllib.load(open('pyproject.toml','rb')); sys.exit(0 if 'importlinter' in d.get('tool',{}) else 1)" 2>/dev/null \
		|| { echo "SKIPPED arch: no [tool.importlinter] contract yet - SPEC 0004 defines it (SPEC 0002 R1.2.6 forbids adding it here)"; exit 0; }; \
	lint-imports

deps:
	deptry $(PKGROOT)

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

## Commit the provenance of a figure that appears in a publication. output/ is gitignored,
## so this copies the kilobytes that make a figure auditable and none of the megabytes.
##   make promote RUN=output/<run-dir> NOTE="thesis ch4 fig 3"
promote:
	@test -n "$(RUN)" || { echo "usage: make promote RUN=output/<run-dir> NOTE=\"where it appears\""; exit 2; }
	@test -n "$(NOTE)" || { echo "NOTE is required: say where the figure appears"; exit 2; }
	python scripts/promote_run.py "$(RUN)" --note "$(NOTE)" $(PROMOTE_FLAGS)

## Phase 8 onward.
docs:
	sphinx-build -W --nitpicky -b html docs docs/_build/html

clean:
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
