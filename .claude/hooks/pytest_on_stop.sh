#!/usr/bin/env bash
# Run the suite at end of turn and surface the result. Non-blocking by default.
out=$(pytest -q 2>&1); code=$?
if [ "$code" -ne 0 ]; then
  echo "pytest FAILED (exit $code):"
  echo "$out" | tail -n 20
  # Hard gate option: replace the final exit with `exit 2` to send Claude back to fix.
fi
exit 0
