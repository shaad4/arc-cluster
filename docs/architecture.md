# ARC architecture

ARC is the monitoring/control plane; Ray is the distributed Python execution
engine. ARC does not replace Ray or manage unrelated services.

## Process boundaries

One unprivileged FastAPI process serves `/api/*`, OpenAPI, compiled frontend
assets, and SPA routes. Its lifespan owns exactly one central monitoring task,
one Ray bridge child process, pooled HTTP clients, and bounded in-memory history.
Run a single Uvicorn worker. Browser polling reads cached samples and never
initializes Ray or triggers a duplicate sampling loop.

The React shell uses TanStack Query with five-second polling, shared query keys,
request cancellation, typed response interfaces, and explicit error/loading states.
Route-level bundles and locally hosted fonts avoid external runtime dependencies.
Recharts plots observed samples without synthesizing missing values. Aggregates
show reporting coverage. Theme and sidebar state are browser presentation only.

## Ray bridge

`backend/arc/services/bridge.py` launches `bridge/worker.py` with
`/data/cluster/venv/bin/python`. JSON-lines messages use stdout; Ray logs are kept
out of the protocol. There is one serialized request at a time, a 4 MiB stream
limit, and a configurable total deadline. A hung bridge is terminated and reaped;
only ARC's child is stopped, never Ray infrastructure. The next sample reconnects.

The bridge reuses `ray.init(address=..., namespace="arc-monitor")`. `ray.nodes()`,
`cluster_resources()`, and `available_resources()` supply actual membership and
logical capacity. The State API supplies task/actor state with strict incomplete
output handling. These are not inferred from process presence.

Node-pinned `NodeAffinitySchedulingStrategy(soft=False)` tasks sample psutil with
150 ms CPU windows, no retries, and zero requested logical CPUs. Pending metric
tasks are cancelled after three seconds. This is lightweight monitoring work,
not a fabricated capacity estimate. State calls have their own short deadlines.

References: [Ray node-affinity scheduling](https://docs.ray.io/en/latest/ray-core/scheduling/index.html),
[State API](https://docs.ray.io/en/latest/ray-observability/reference/api.html), and
[Jobs SDK concepts](https://docs.ray.io/en/latest/cluster/running-applications/job-submission/jobs-package-ref.html).
Installed Ray 2.60.0 signatures were also inspected directly before implementation.

## Collection and data semantics

The sampler concurrently requests a bridge snapshot, local psutil metrics in a
thread, and configured worker-agent observations. Local metrics remain possible
when Ray is unavailable. Agent requests have short timeouts and at most five
connections. History is a deque capped at 720 samples and one hour; events are
capped at 200. No database or external metrics service is needed.

Physical memory uses total minus available; CPU aggregation weights each machine
by its reported CPU count. Network rates use counter deltas and elapsed sample
time. The first sample, reset counters, and missing measurements yield null rates.
Fresh measurements only are aggregated. Old measurements can remain attached to
node records with an explicit stale flag and timestamp, but are not plotted as
new measurements.

Inventory is five configured machines. A live Ray registration is preferred over
older dead IDs for the same IP. Ray disconnection and machine reachability are
separate states. Agent failure is not sufficient to assert that the VM is off.
Recovery failures are reported rather than hidden behind a success notification.

## Jobs and logs

Jobs use the local Ray dashboard HTTP API with a pooled HTTPX client, bounded
responses, request deadlines, and five-second shared caching. Job/driver identity
is distinct from tasks and actors. The approved-workload endpoint validates a
fixed workload ID and strict integer parameter, then constructs a server-owned
entry point. It is disabled by default and requires UI confirmation.

Node logs use an allowlist (`raylet.out`, `raylet.err`), never arbitrary browser
paths. Reads are tails, not whole-file loads. Secret-looking lines and private-key
blocks are redacted. Remote log content gets redacted again on the controller.
No request bodies, bearer tokens, or environment dictionaries are logged.

## Agents and controls

Each optional worker agent runs from its own environment under a non-root user,
binds only its Tailscale IP, and requires a strong per-worker bearer token plus
an exact controller peer IP. Tailscale supplies transport encryption and network
ACLs; HTTP is not exposed publicly. Credentials are loaded from mode-0600 files.

Before control execution, the agent queries independent Ray State/Jobs APIs using
the existing Ray interpreter. Incomplete observations, active tasks/actors/jobs,
unknown process state, and missing connectivity block actions. Head operations
are denied. `start`, `stop`, and `recover` map to fixed `ray` argv arrays without
a shell. The browser cannot submit executable strings. Each agent and the
controller serialize mutations; the agent rechecks before running commands.

The controller verifies membership using samples newer than command completion.
Unverified outcomes are not called successes. Preflight cannot provide an atomic
cluster-wide scheduling lock; the operator must prevent concurrent workload
submission during worker management. Remote operation is unverified until agents
and their independent State API path are deployed and exercised by the operator.

## Security and deployment

Production binding is constrained to `127.0.0.1`. Trusted Host and exact Origin
checks protect mutations, with an additional ARC request header. There is no
wildcard CORS. Root execution is rejected. No SSH keys or sandbox API credentials
are used for worker management. The SPA fallback never swallows unknown API paths.

`manage.py` offers owned-process foreground/background lifecycle management;
optional user-systemd units are provided. Both stop only ARC and allow its lifespan
to close clients, cancel its sampler, and terminate its bridge. Rotating application
logs are bounded. The application survives Ray failure; process-local history does
not survive an ARC restart or an InstaBox lifecycle event.
