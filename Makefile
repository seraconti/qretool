# mypy is scoped to the layering root AGENTS.md names, not the whole package. Widening it
# is deferred: the modules outside this tree do not type-check yet.
PKG := src/quebra/core
FAST := -m "not slow and not heavy and not real and not r"

.PHONY: check check-ci lint types arch deps test test-all test-r test-real promote docs clean

## Run before every checkpoint. This is what the checkpoint banner reports.
check: lint types arch test

## Run the same gate against a clean dependency resolve in a throwaway environment, which
## is what the workflow does. `check` uses the installed tools, so it cannot see a failure
## caused by a newer release or by the install being non-editable. Run before pushing.
check-ci:
	bash scripts/check_ci.sh

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

## Local only: `real` needs data/real_private/, and `regression` compares against values
## pinned from a run over it, so neither may execute on a public runner.
##
## The target line is load-bearing. Without it this recipe attaches to `test-r`, and the
## private-data selector rides along with whatever calls the R target. That exposure is
## latent, not live: `pytest -m "r"` exits 5 first and make stops on it. It goes live the
## moment any test carries the `r` marker.
##
## Both selectors match no test, so both exit 5. That failure is deliberate - a target
## reporting "selected nothing" as success is how an unrun tier rots unnoticed. `regression`
## is additionally not a declared marker: it evaluates false in a `-m` expression, and
## `--strict-markers` will reject the first test that carries it.
test-real:
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
