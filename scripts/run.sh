#!/usr/bin/env bash
set -euo pipefail
ARC_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ARC_ROOT"
if [ "$(id -u)" = 0 ]; then
  echo 'Run ARC as an unprivileged user.' >&2
  exit 1
fi
if [ ! -f frontend/dist/index.html ]; then
  echo 'Build the frontend first: cd frontend && npm ci && npm run build' >&2
  exit 1
fi
exec "$ARC_ROOT/backend/.venv/bin/python" -m arc
