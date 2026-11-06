#!/usr/bin/env bash
# Run explicitly on a worker with a copy of this repository. Does not start Ray.
set -euo pipefail
ARC_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [ "$(id -u)" = 0 ]; then echo 'Run as an unprivileged user.' >&2; exit 1; fi
python3 -m venv "$ARC_ROOT/agent-venv"
"$ARC_ROOT/agent-venv/bin/python" -m pip install "$ARC_ROOT/backend"
echo 'Agent environment installed. Configure private credentials and agent.env as documented.'
echo 'No agent service or Ray process has been started or modified.'
