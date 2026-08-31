# The src/ layout landed in SPEC 0002. mypy checks the layering root AGENTS.md section 3
# names; widening it to the whole package is a later phase with its own checkpoint.
PKG := src/quebra/core
FAST := -m "not slow and not heavy and not real and not r"

.PHONY: check lint types arch deps test test-all test-r test-real promote docs clean

## Run before every checkpoint. This is what the checkpoint banner reports.
check: lint types arch test

lint:
	ruff check .
	ruff format --check .

types:
	mypy $(PKG)

## Dependency direction. The contract lives in [tool.importlinter]; 
##
## `--no-cache` needed: `.import_linter_cache` can serve a graph built before a
## module MOVED, and the cache file is then newer than the sources it misdescribes, so
## nothing invalidates it
arch:
	lint-imports --no-cache

deps:
	deptry .

test:
	pytest $(FAST)

## Everything a laptop can run without private data.
test-all:
	pytest -m "not real"

## Separate CI job. Requires Rscript plus copula and randtests.
test-r:
	pytest -m "r"

## Local only. Touches data/real_private/. not on github actions
	pytest -m "real or regression"

## Commit the provenance of a figure that appears in a publication. output/ is gitignored,
## so this copies the kilobytes that make a figure auditable and none of the megabytes.
##   make promote RUN=output/<run-dir> NOTE=""
promote:
	@test -n "$(RUN)" || { echo "usage: make promote RUN=output/<run-dir> NOTE=\"where it appears\""; exit 2; }
	@test -n "$(NOTE)" || { echo "NOTE is required: say where the figure appears"; exit 2; }
	python3 scripts/promote_run.py "$(RUN)" --note "$(NOTE)" $(PROMOTE_FLAGS)

## future integration of sphinx, currently unsupported
docs:
	sphinx-build -W --nitpicky -b html docs docs/_build/html

clean:
	rm -rf .import_linter_cache
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
