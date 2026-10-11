#!/usr/bin/env bash
# Run every gui_paint check on both supported Blender targets.
#
# Usage:
#   tests/run.sh              # runs every tests/check_*.py
#   tests/run.sh <check.py>   # runs only the given checks
#
# Override the binaries with BLENDER_42 / BLENDER_52.
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BLENDER_42="${BLENDER_42:-/opt/blender/blender-4.2.23-linux-x64/blender}"
BLENDER_52="${BLENDER_52:-/opt/blender/blender-5.2.2-linux-x64/blender}"

CHECKS=()
for arg in "$@"; do
  CHECKS+=("$arg")
done
if [ "${#CHECKS[@]}" -eq 0 ]; then
  for candidate in "$ROOT"/tests/check_*.py; do
    [ -f "$candidate" ] && CHECKS+=("$candidate")
  done
fi

if [ "${#CHECKS[@]}" -eq 0 ]; then
  echo "no checks found under $ROOT/tests"
  exit 1
fi

# --factory-startup: without it the user's Skybrush extension raises in
#   load_post during every background run.
# --python-exit-code 1: Blender exits 0 after a Python exception otherwise,
#   which would make this harness silently green.
BLENDER_ARGS=(--background --factory-startup --python-exit-code 1)

failures=0
for entry in "4.2:$BLENDER_42" "5.2:$BLENDER_52"; do
  label="${entry%%:*}"
  binary="${entry#*:}"
  for check in "${CHECKS[@]}"; do
    name="$label $(basename "$check")"
    if [ ! -x "$binary" ]; then
      echo "FAIL $name - no such binary: $binary"
      failures=$((failures + 1))
      continue
    fi
    if output="$("$binary" "${BLENDER_ARGS[@]}" --python "$check" 2>&1)"; then
      echo "ok   $name"
    else
      echo "FAIL $name"
      printf '%s\n' "$output" | tail -25
      failures=$((failures + 1))
    fi
  done
done

echo "---"
if [ "$failures" -eq 0 ]; then
  echo "all checks passed"
else
  echo "$failures check(s) failed"
  exit 1
fi
