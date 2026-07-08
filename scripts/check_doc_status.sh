#!/usr/bin/env bash
# Fail CI if canonical docs drift back to stale status phrases.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PATTERN='Scaffolding stage|segmentation, classification, and COG I/O are not yet implemented|API stubs'

_stale_hits() {
  grep -nE "$PATTERN" "$ROOT/README.md" "$ROOT/docs/architecture.md" 2>/dev/null || true
}

if [ -n "$(_stale_hits)" ]; then
  echo "Stale implementation-status language found in README or architecture.md."
  echo "Update docs/IMPLEMENTATION_STATUS.md and remove contradictory claims."
  _stale_hits
  exit 1
fi

if ! grep -q 'IMPLEMENTATION_STATUS' "$ROOT/README.md" "$ROOT/docs/architecture.md"; then
  echo "README.md and docs/architecture.md must link to docs/IMPLEMENTATION_STATUS.md"
  exit 1
fi

echo "Doc status guardrail passed."
