#!/usr/bin/env bash
# Clean-environment acceptance for SPEC 0002 R1.4.1.
#
# The claim this phase makes is "a reviewer runs the documented install steps on a machine
# that has never seen this repository". This script is the only thing that can falsify it:
# every other gate runs against the editable install, where `src/` is on the path and a
# packaging mistake is invisible.
#
# The virtualenv is created OUTSIDE the repository on purpose. Inside it, `pip install`
# might resolve the source tree instead of the wheel, and the test would pass while proving
# nothing.
#
# Exit codes are printed per step rather than only propagated, so a failure says which step
# failed without reading the whole log.
set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SANDBOX="$(mktemp -d)"
VENV="${SANDBOX}/venv"
# Somewhere that is emphatically not the repository, and has no project marker of its own.
OUTSIDE="${SANDBOX}/elsewhere"
mkdir -p "${OUTSIDE}"
STATUS=0

step() {
  local name="$1"; shift
  echo ""
  echo "=== ${name} ==="
  "$@"
  local code=$?
  echo "--- ${name}: exit ${code}"
  [ "${code}" -ne 0 ] && STATUS=1
  return 0
}

echo "repo:  ${REPO}"
echo "venv:  ${VENV}"
echo "cwd:   ${OUTSIDE}"

step "build the wheel" env -C "${REPO}" python3 -m build --outdir "${REPO}/dist"

WHEEL="$(ls -t "${REPO}"/dist/*.whl 2>/dev/null | head -1)"
if [ -z "${WHEEL}" ]; then
  echo "no wheel produced; stopping"
  exit 1
fi
echo "wheel: ${WHEEL}"

step "create the venv"  python3 -m venv "${VENV}"
step "install the wheel" "${VENV}/bin/pip" install --quiet "${WHEEL}"
step "install pytest"    "${VENV}/bin/pip" install --quiet pytest

# Imported from a directory that is NOT the repository, so a stray relative path or a
# leftover `sys.path` entry cannot mask a packaging error.
step "import quebra from elsewhere" env -C / "${VENV}/bin/python" -c \
  "import quebra, quebra.core.paths, quebra.cli; print('quebra', quebra.__file__)"

step "the console script exists" env -C / "${VENV}/bin/quebra" --help

# The suite lives in the checkout - `tests/` is deliberately not in the wheel - but it runs
# from a DIRECTORY THAT IS NOT THE REPOSITORY, because that is the claim the spec makes:
# "import quebra works from an unrelated working directory, the fast test suite passes
# there". An earlier version of this script ran the step with `env -C "${REPO}"` and passed
# while six tests failed from anywhere else, so the gate concealed exactly the gap it was
# written to expose. Pinning the cwd to the repository is the one thing this step must not
# do.
step "fast test selector from an unrelated cwd" env -C "${OUTSIDE}" "${VENV}/bin/python" -m pytest \
  -m "not slow and not heavy and not real and not r" -q "${REPO}/tests"

echo ""
echo "=================================="
echo "acceptance: exit ${STATUS}"
exit "${STATUS}"
