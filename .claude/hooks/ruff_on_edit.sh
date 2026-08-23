#!/usr/bin/env bash
# Format + lint-fix the Python file just edited. Non-blocking. Needs python3 + ruff on PATH.
file=$(python3 -c 'import sys,json; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))' 2>/dev/null)
[ -z "$file" ] && exit 0
case "$file" in
  *.py)
    ruff check --fix "$file" >/dev/null 2>&1
    ruff format "$file" >/dev/null 2>&1
    ;;
esac
exit 0
