# Optional worker-agent installation

Deployment is pending on box2–box5. This guide is an explicit operator procedure,
not evidence that ARC has remote SSH access. Do not install an agent on box1;
local metrics already work and head controls are disabled.

## 1. Install on a worker

Use an already authorized worker terminal/connection. Transfer this repository
without `.git`, `.venv`, `.runtime`, frontend dependencies, or secret files, or
clone the approved repository once its changes have been published by the owner.
The implementation session does not push code or copy laptop credentials.

```bash
cd /data/projects/cluster-monitor
./scripts/install-agent.sh
mkdir -p ~/.config/arc
chmod 700 ~/.config/arc
```

The script creates `/data/projects/cluster-monitor/agent-venv` and installs ARC
there. It does not touch `/data/cluster/venv`, start a service, or change Ray.

## 2. Provision per-worker credentials

Use a distinct cryptographically random token of at least 32 characters for each
worker. Example generation on the worker writes a protected file without printing
the secret:

```bash
python3 - <<'PY'
import json, os, secrets
from pathlib import Path
path = Path.home() / '.config/arc/agent-token.json'
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as stream:
    json.dump({'token': secrets.token_urlsafe(48)}, stream)
PY
```

Through an approved private secret-transfer mechanism, provision the corresponding
value on box1 in `~/.config/arc/agents.json` as a JSON mapping from node names to
tokens. Do not paste secrets into chat, shell command arguments, logs, or Git.
Example **shape**, not usable credentials:

```json
{"box2":"<box2 token>","box3":"<box3 token>"}
```

Both files must be owned by their service user and mode 0600. Set on box1:
`ARC_AGENT_CREDENTIALS_FILE=/data/home/.config/arc/agents.json` (adjust to the actual
user home), then restart ARC only.

## 3. Restrict network access

Authorize only box1's `100.118.85.127` identity/IP to each worker's TCP 9071 in
Tailscale ACLs. The application also enforces that controller peer IP. Do not
forward this port publicly. No laptop SSH private keys or InstaBox tokens are
required or accepted.

For box2, create `~/.config/arc/agent.env` (mode 0600):

```dotenv
ARC_AGENT_BIND=100.124.19.50
ARC_AGENT_CONTROLLER=100.118.85.127
ARC_AGENT_TOKEN_FILE=/data/home/.config/arc/agent-token.json
ARC_AGENT_ENABLE_CONTROLS=0
```

Use the correct worker IP and actual absolute home path. `ARC_AGENT_BIND` must be
the local worker's Tailscale address, not `0.0.0.0`. Leave controls disabled to
start with read-only metrics and allowlisted logs.

To run in the foreground, export these non-secret path/config values, then:

```bash
agent-venv/bin/python -m arc.agent.main
```

Or explicitly install the optional user service:

```bash
mkdir -p ~/.config/systemd/user
cp deploy/arc-agent.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now arc-agent.service
```

This is operator work; no unit has been installed automatically. ARC Settings
should then show the agent online, and a disconnected Ray worker can still report
physical metrics. If not, inspect credentials, permissions, ACL, and worker runtime.

## 4. Independent safety-check access before enabling controls

Controls require a worker-local path to the head's Ray dashboard State/Jobs APIs
that works even when that worker is disconnected from Ray. The existing head
dashboard is loopback-only. **Do not rebind/restart it or expose it publicly.**

If worker-to-head SSH is separately provisioned and approved, an unprivileged
forward can provide this path on the worker:

```bash
# On that worker, only after independently authorizing its SSH access to box1:
ssh -N -L 18265:127.0.0.1:8265 box1
```

This is not assumed to work today. Provision dedicated restricted SSH access via
your existing administrative process; never copy a laptop private key. Other
private access designs require operator review and narrow access controls.

Only after that connection is verified, add to the worker environment:

```dotenv
ARC_AGENT_STATE_URL=http://127.0.0.1:18265
ARC_AGENT_ENABLE_CONTROLS=1
```

Restart the **agent only**. ARC's Check safety button will now attempt independent
membership, task, actor, submission-job, and process checks. Any unavailable or
truncated State API result blocks controls. A running actor blocks management even
when idle; this conservative behavior is intentional. The controller rechecks at
execution time and verifies fresh Ray membership after the command.

## 5. Operator validation

During an approved maintenance window, stop new workload submissions, inspect the
node, run Check safety, and explicitly confirm the desired operation. `recover`
is only for a disconnected worker; it refuses live members. The stop command is
non-forced (`ray stop --grace-period=5`). No example workload or worker operation
was run during development. A real end-to-end management test remains pending
agent deployment and operator authorization.

ARC cannot bypass a paused InstaBox, runtime limits, cooldowns, or missing network
access. Unreachable agents remain unavailable; they do not produce fake metrics.
