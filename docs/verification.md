# Implementation verification — 6 November 2026

## Result

ARC is running as the normal box1 user through `scripts/manage.py`, listening only
on `127.0.0.1:8000`. FastAPI serves the built React application and real monitoring
APIs. All seven pages and node detail routes were exercised in Chromium. No Ray
services were stopped/restarted, no worker controls or example submissions were
executed, and no Git push was performed.

## Executed validation

| Check | Result |
| --- | --- |
| Backend pytest suite | 19 passed |
| Ruff lint and formatting | Passed |
| Frontend Vitest suite | 4 passed |
| TypeScript | Passed through typecheck and production build |
| ESLint | Passed |
| Vite production build | Passed; route-split main JS ~341 KB, charts ~365 KB |
| Live Playwright desktop/mobile tests | 2 passed |
| npm audit | 0 reported vulnerabilities |
| Local HTTP smoke checks | All 25 checked page/API routes returned HTTP 200 |
| Listener inspection | 127.0.0.1:8000 only |
| Startup/restart/health-check scripts | Executed successfully |
| User systemd availability | Reported running; units provided but not installed |
| Documentation relative links | Validated |

Tests cover API liveness, inventory, actual membership semantics, Ray failure,
agent unavailability/authentication, bridge timeouts and process cleanup, stale
metrics/membership, invalid identifiers, unsafe recovery rejection, job errors and
caching, mutation protection, production routing, loading/error/offline UI states,
confirmation dialogs, live navigation, node details, theme switching, and mobile
layout. External infrastructure is mocked for isolated backend tests.

Read-only integration checks used the existing Ray 2.60.0 environment. At final
inspection, the configured inventory had five machines but Ray had one active
configured member: box1, 4 CPU resources. Box1 supplied actual CPU, memory, disk,
network, hostname, and uptime measurements. Workers box2–box5 had dead Ray
registrations and unknown independent machine status. These are observations,
not claims that those machines are powered off. The workload State API returned
76 task records with no incomplete-output error after excluding ARC metric probes.
The Jobs API returned 15 driver records and no submission jobs at that inspection.
Counts and measurements naturally change over time.

Screenshots from live browser tests:
- `/tmp/arc-overview.png`
- `/tmp/arc-mobile.png`

## Explicitly unverified or pending

- Worker agents are implemented but not deployed on box2–box5. Per-worker tokens,
  Tailscale ACLs, and independent private State API access require operator setup.
- Start, stop, recovery, and example submission code were not exercised against
  live infrastructure. Safety rejection paths were tested; destructive success
  paths require an operator-authorized maintenance window.
- Real submission-job log retrieval could not be exercised because no submission
  jobs were present. The bounded API path is implemented; driver jobs are shown
  distinctly and node logs are accessible.
- Laptop-side SSH tunnel connectivity cannot be verified from this VM. Local HTTP
  and browser behavior are verified; use the existing `box1` SSH alias.
- No systemd unit was installed/enabled. The unprivileged background manager is
  the active deployment; user-systemd installation instructions are provided.
- History is process-local and resets on restart. Safety preflight is not an atomic
  scheduler lock; prevent concurrent workload submissions during management.

## Commands

```bash
cd /data/projects/cluster-monitor
python3 scripts/manage.py status
./scripts/health-check.sh
# Start if stopped:
python3 scripts/manage.py start
# Restart ARC only:
python3 scripts/manage.py restart
```

From the laptop:

```bash
ssh -N -L 8000:127.0.0.1:8000 box1
```

Open `http://127.0.0.1:8000`; API docs are at `/docs`.
See [README](../README.md), [architecture](architecture.md), and
[worker-agent setup](worker-agents.md) for complete instructions.

## Implementation commits

Local commits since the initial health-endpoint foundation, in chronological order
(the subsequent documentation commit records this report):

```text
d095390 docs: extend engineering rules for full ARC implementation
c365fab feat: add isolated persistent Ray monitoring bridge
b026f7d feat: collect live node metrics and bounded cluster history
de008b1 feat: add restricted Ray jobs and bounded log retrieval
aba1eaf feat: add authenticated worker agents and fail-closed recovery controls
5f332f4 feat: expose safe collector settings and service status
7758ecf feat: build ARC dashboard shell and live overview
bc2dd68 feat: add node inventory details and confirmation controls
4c2415d feat: visualize Ray state and historical machine metrics
6109596 feat: add Ray job inspection and approved workload dialog
b3716e7 fix: derive running job duration from query refresh time
9423652 feat: add searchable centralized log viewer
818aae8 feat: add configuration and collector status page
64da460 feat: serve production frontend with loopback security defaults
b63000b fix: cache job observations and require fresh control verification
38d2a22 chore: patch frontend tooling dependencies and add browser test tools
ff8ca84 style: format frontend source for maintainability
04ca5d0 fix: resolve production frontend from repository root
a41e6ac chore: add unprivileged deployment and health-check scripts
78f9377 test: verify live dashboard navigation and mobile layout
f8edb55 test: cover agent authentication and infrastructure failure paths
29eb09f perf: split page bundles and trim font assets
9ad956e fix: bound service logs and queued job request timeouts
c1050a9 fix: expire stale Ray membership and resource observations
c3671ee fix: redact credential-shaped values from bounded log tails
9c8e306 feat: report active recovery and failed management events
1bf8b24 feat: add node table action menus
ad69687 docs: document architecture deployment and worker agent setup
305e5af perf: exclude monitoring probes from Ray workload queries
```
