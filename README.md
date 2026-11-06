# ARC

**Distributed Compute Control Plane — One control plane. Every node.**

ARC is a private, self-hosted monitoring and control dashboard for a five-machine
Ray cluster. FastAPI serves a React production build on `127.0.0.1:8000` on box1.
There is no application login; access is through an SSH tunnel. Ray remains the
execution engine. ARC is not a container scheduler or a general service orchestrator.

## Features

- Overview with actual Ray CPU resources, physical machine metrics, collection
  coverage, recent status transitions, and live history.
- Five-node inventory with search/filter/sort, separate machine and Ray states,
  node details, CPU/RAM/disk/network measurements, and uptime.
- Ray membership, logical resource allocations, tasks, and actors.
- Ray Jobs inspection, bounded logs, and an explicitly approved example workload.
- Metrics views for 5 minutes, 15 minutes, or 1 hour; bounded in-memory history.
- Allowlisted centralized logs with search, text severity filters, copy, and polling.
- Settings and runtime polling controls. Dark/light themes and responsive navigation.
- Optional authenticated worker agents; worker controls fail closed unless
  independent safety checks succeed. Head controls are disabled.

All production metrics come from the machines or Ray. A missing metric is **not
zero**. Machine status `unknown` means ARC has no current independent evidence;
a dead Ray registration alone does not establish that a machine is offline.

## Architecture and stack

```text
Laptop browser → SSH tunnel → 127.0.0.1:8000 (box1)
                              FastAPI + compiled React
                                ├─ one central sampler → bounded RAM history
                                ├─ local psutil collector
                                ├─ persistent JSON-lines Ray bridge
                                │    /data/cluster/venv/bin/python
                                │    → Ray membership/resources/State API
                                │    → node-pinned metric tasks
                                ├─ bounded HTTP Ray Jobs client → localhost:8265
                                └─ authenticated agent clients → worker Tailscale IPs
```

Python 3.13, FastAPI, Pydantic v2, asyncio, psutil, HTTPX; React, TypeScript, Vite,
Tailwind CSS, shadcn-style Radix components, Lucide, Recharts, TanStack Query,
React Router, and locally bundled Geist fonts. See [architecture](docs/architecture.md).

## Cluster configuration

| Node | Role | Tailscale address |
| --- | --- | --- |
| box1 | Head + worker | 100.118.85.127 |
| box2 | Worker | 100.124.19.50 |
| box3 | Worker | 100.64.151.60 |
| box4 | Worker | 100.93.80.83 |
| box5 | Worker | 100.96.223.107 |

Nominal hardware: 4 vCPUs, ~7.8 GiB physical RAM, and ~20 GiB `/data` storage per
machine. These are independent resources, not one shared-memory/storage system.
The dashboard displays observed capacity, which can be lower than the nominal
20 CPUs / ~39 GiB RAM. Inventory is defined in `backend/arc/services/monitor.py`.

Ray 2.60.0 is already installed at `/data/cluster/venv`. ARC does not install into
that environment. Head: `100.118.85.127:6379`; existing Ray dashboard:
`http://127.0.0.1:8265`. Do not restart or rebuild Ray to deploy ARC.

## Install and build

Run as the normal non-root box1 user. Check free disk space first (`df -h /data`).
Requires Python 3.13+, Node 22.12+ (tested with 22.23.3), and npm.

```bash
cd /data/projects/cluster-monitor
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -e './backend[dev]'
cd frontend
npm ci
npm run build
cd ..
```

The isolated backend environment and generated frontend build are ignored by Git.
The frontend package lock pins the tested dependency graph. Ray is deliberately
absent from ARC's dependencies; the bridge uses the existing Ray interpreter.

## Start, stop, and access

Foreground (Ctrl+C stops ARC only):

```bash
cd /data/projects/cluster-monitor
./scripts/run.sh
```

Unprivileged background alternative, used for the verified local deployment:

```bash
python3 scripts/manage.py start
python3 scripts/manage.py status
./scripts/health-check.sh
python3 scripts/manage.py restart
# Stop ARC only:
python3 scripts/manage.py stop
```

The manager verifies both PID identity and process start time before stopping a
process. Logs live in ignored `.runtime/`: `arc.log` rotates at 1 MiB with two
backups; `bootstrap.log` captures startup failures. Do not run two ARC instances
against the same port. Use one backend worker: each process owns a sampler.

From the Ubuntu laptop, assuming the existing `box1` SSH alias works:

```bash
ssh -N -L 8000:127.0.0.1:8000 box1
```

- Dashboard: <http://127.0.0.1:8000>
- API documentation: <http://127.0.0.1:8000/docs>
- Application liveness: <http://127.0.0.1:8000/api/health>

A laptop SSH session cannot be verified from inside this VM. The local listener,
HTTP API, and browser navigation have been verified. No public tunnel is needed.

### Optional user systemd service

The provided unit is a **user** service, not a privileged system service. Its
installation is an explicit operator step; implementation did not install it.
Stop the background manager first to avoid a port conflict.

```bash
python3 scripts/manage.py stop
mkdir -p ~/.config/systemd/user ~/.config/arc
cp deploy/arc.service ~/.config/systemd/user/arc.service
# Optional: copy .env.example to ~/.config/arc/arc.env, edit it, and chmod 600 it.
systemctl --user daemon-reload
systemctl --user enable --now arc.service
systemctl --user status arc.service
# After future builds or configuration changes:
systemctl --user restart arc.service
journalctl --user -u arc.service -n 100
```

User services depend on the sandbox's user-manager/session lifetime. No lingering,
privileged installation, or changes to InstaBox lifecycle limits are performed.
Use foreground/background operation when user systemd is unavailable.

## Configuration and development

[.env.example](.env.example) documents supported environment variables. ARC reads
exported variables; it does not implicitly read `.env` files. Systemd can use the
optional `~/.config/arc/arc.env` EnvironmentFile. Keep it mode 0600.

Important defaults: `ARC_POLL_INTERVAL=5`, `ARC_STALE_AFTER=20`,
`ARC_BRIDGE_TIMEOUT=15`, `ARC_APPROVED_WORKLOAD=false`. The UI can change polling
from 5–60 seconds for the current process. Persist changes via service environment;
if choosing slower sampling, adjust the stale threshold as appropriate.

For local development, run the backend and `cd frontend && npm run dev`.
Vite proxies `/api` to localhost:8000. Use the production localhost:8000 origin to
exercise mutations; strict origin validation can reject development-proxy writes.
No wildcard CORS or public bind address is supported.

## Worker agents and recovery

See the complete [worker-agent installation guide](docs/worker-agents.md).
Agents are optional and have **not been installed on the workers**. Without one,
Ray can still supply metrics for a live member; a disconnected worker's physical
metrics and controls remain unavailable. ARC never assumes SSH access to workers.

Recovery requires an authenticated agent, independent State API access, complete
workload observations, no active tasks/actors/submission jobs, and confirmation.
The agent rechecks immediately before invoking fixed commands. A healthy Ray
member is never restarted by `recover`. ARC verifies fresh membership afterward;
a command whose effect cannot be verified is reported `unverified`, not success.

No start/stop/recover actions or example jobs were executed during development.

## Approved example workload

Only `distributed-square` is allowlisted. An operator must explicitly set
`ARC_APPROVED_WORKLOAD=true` and restart ARC before the UI enables submission.
The browser accepts only an integer count from 1 to 100 and confirmation. The
server constructs the fixed entry point; no shell commands or arbitrary runtime
environments can be supplied. Tasks request 0.25 Ray CPUs each. Do not enable or
run this example when it would interfere with existing workloads.

Driver jobs, submission jobs, tasks, and actors are separate concepts. Job logs
are available for submission IDs; driver execution may require node logs.

## API reference

Interactive schemas and response types: `/docs`, `/openapi.json`.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Application liveness, version, UTC timestamp; no Ray claim |
| GET | `/api/cluster/overview` | Inventory, aggregate coverage, Ray state, events |
| GET | `/api/cluster/nodes` | Five configured nodes |
| GET | `/api/cluster/resources` | Actual Ray capacity/availability |
| GET | `/api/cluster/events` | Last 200 observed transitions/actions |
| GET | `/api/nodes/{node_id}` | Machine and Ray details |
| GET | `/api/nodes/{node_id}/metrics` | Metrics plus source/staleness metadata |
| GET | `/api/nodes/{node_id}/logs` | Allowlisted node log tail |
| GET | `/api/nodes/{node_id}/preflight` | Independent worker safety check |
| POST | `/api/nodes/{node_id}/refresh` | Request centralized collection |
| POST | `/api/nodes/{node_id}/ray/start` | Confirmed allowlisted start |
| POST | `/api/nodes/{node_id}/ray/stop` | Confirmed allowlisted worker stop |
| POST | `/api/nodes/{node_id}/recover` | Confirmed disconnected-worker recovery |
| GET | `/api/ray/status` | Membership and logical resources |
| GET | `/api/ray/tasks`, `/api/ray/actors` | State API observations/errors |
| GET | `/api/jobs` | Cached Ray Jobs inventory |
| GET | `/api/jobs/{job_id}` | Job detail |
| GET | `/api/jobs/{job_id}/logs` | Bounded, redacted job log response |
| POST | `/api/workloads/submit` | Approved example only |
| GET | `/api/metrics/cluster` | Fresh physical aggregates |
| GET | `/api/metrics/history?minutes=5` | Samples; 1–60 minute query bound |
| GET | `/api/logs` | Node/source/search/text-severity filters |
| GET, PATCH | `/api/settings` | Safe public settings / polling update |

Mutations require exact localhost `Origin`, `X-ARC-Request: 1`, and valid Host.
Controls require `{"confirmed":true}`. There is no arbitrary command endpoint.
Errors use HTTP status codes and `detail`; incomplete collector data remains
explicit in snapshots instead of inventing successful observations.

## Validation and screenshots

```bash
backend/.venv/bin/python -m pytest backend/tests -q
backend/.venv/bin/ruff check backend scripts/manage.py
backend/.venv/bin/ruff format --check backend scripts/manage.py
cd frontend
npm run typecheck
npm run lint
npm test
npm run build
# With production ARC already running and Chromium installed:
npm run test:e2e
# Or headless:
INSTABOX_HEADLESS=1 npm run test:e2e
npm audit
```

Browser tests visit all seven pages, node detail routes, both themes, and mobile
navigation. They inspect disabled controls but never perform management actions.
They save `/tmp/arc-overview.png` and `/tmp/arc-mobile.png`; test failures save
screenshots under ignored `frontend/test-results`. Tests use `/usr/bin/chromium`;
change the Playwright config for another workstation.

## Troubleshooting and limitations

- **Only one node/4 CPUs:** this can be the true current membership. Check Nodes;
  do not interpret the nominal inventory as live capacity or restart Ray blindly.
- **Ray unavailable:** inspect the existing head/dashboard and bridge interpreter
  path. ARC stays accessible and retries. Existing Ray services are not changed.
- **Unknown worker:** independent agent monitoring is not configured or reachable.
  This is not proof of a powered-off machine.
- **Controls disabled:** review the preflight reason, agent credential permissions,
  Tailscale ACL, independent State API access, and active workloads.
- **503 on pages:** build `frontend/dist` or set `ARC_FRONTEND_DIST` correctly.
- **Port busy:** stop the other ARC instance, not Ray. Use `ss -ltnp` to inspect.
- **History gaps/reset:** collection can time out; stale data is excluded. History
  is bounded and process-local, not durable observability storage.
- **State limits:** tasks/actors are limited to 1,000 records; incomplete results
  are flagged unavailable. Agent safety checks allow 10,000 and reject truncation.
- **Logs:** only Raylet output/errors and ARC events are exposed. Tails are capped
  at 500 lines/64 KiB. Jobs API responses over 1 MiB are rejected rather than loaded
  without bounds. Sensitive-looking lines are conservatively redacted; avoid
  writing secrets into application logs in the first place.
- **Safety race:** preflight is conservative but is not a Ray scheduling lock.
  Operators must avoid concurrent job submission during management. No automated
  restarts or destructive lifecycle actions run in the background.
- **Monitoring overhead:** node tasks use zero logical Ray CPUs but consume a small
  amount of physical CPU; samples measure over 150 ms. Browser QA itself uses more
  resources than the steady-state sampler.

## Security and roadmap

Keep ARC loopback-only and tunnel it. Keep agents on Tailscale, with per-node
service tokens and narrow ACLs. Do not copy laptop SSH private keys or InstaBox
API tokens. Secret files are outside Git and must be owned by the service user
with mode 0600. Neither ARC nor agents run as root. No privileged service was
enabled and no remote agent was deployed by this implementation.

Future work: operator-authorized worker-agent rollout, stronger coordinated drain
semantics, configurable inventory UI, durable optional history, richer approved
workloads, and additional read-only log sources. General web-application/service
deployment would require a separate orchestration layer.
