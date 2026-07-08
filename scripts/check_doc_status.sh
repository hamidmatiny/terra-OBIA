#!/usr/bin/env bash
# Fail CI if canonical docs drift back to stale status phrases.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PATTERN='Scaffolding stage|segmentation, classification, and COG I/O are not yet implemented|API stubs'

if rg -n "$PATTERN" "$ROOT/README.md" "$ROOT/docs/architecture.md" >/dev/null 2>&1; then
  echo "Stale implementation-status language found in README or architecture.md."
  echo "Update docs/IMPLEMENTATION_STATUS.md and remove contradictory claims."
  rg -n "$PATTERN" "$ROOT/README.md" "$ROOT/docs/architecture.md" || true
  exit 1
fi

if ! rg -q 'IMPLEMENTATION_STATUS' "$ROOT/README.md" "$ROOT/docs/architecture.md"; then
  echo "README.md and docs/architecture.md must link to docs/IMPLEMENTATION_STATUS.md"
  exit 1
fi

echo "Doc status guardrail passed."
