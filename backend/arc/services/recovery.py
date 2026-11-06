"""Optional controller: short leases, fresh independent checks, one action at a time."""

import asyncio
import contextlib
import time
from pathlib import Path

from fastapi import HTTPException

from arc.agent.supervisor import atomic_json
from arc.models.cluster import Event
from arc.models.recovery import (
    AgentPolicy,
    NodeRecoveryStatus,
    RecoveryConfiguration,
    RecoveryStatus,
    RecoveryUpdate,
    SupervisorStatus,
)


class RecoveryController:
    def __init__(self, settings, monitor, agents, control_lock):
        self.settings, self.monitor, self.agents = settings, monitor, agents
        self.control_lock = control_lock
        self.configuration = RecoveryConfiguration()
        self.path = Path(settings.auto_recovery_file)
        self.error = None
        self.states = {
            n.id: NodeRecoveryStatus(node_id=n.id)
            for n in monitor.nodes
            if n.role == "worker"
        }
        self.seen = {}
        self.next_contact = {}
        self.failures = {}
        self.task = None
        self.wake = asyncio.Event()
        self.revision = time.time_ns()
        if self.path.exists():
            try:
                self.configuration = RecoveryConfiguration.model_validate_json(
                    self.path.read_text()
                )
            except (OSError, ValueError):
                self.error = (
                    "Recovery configuration unreadable; automation remains disabled"
                )

    def policy(self, **values):
        self.revision = max(self.revision + 1, time.time_ns())
        return AgentPolicy(revision=self.revision, **values)

    def event(self, node_id, state, message):
        current = self.states[node_id]
        if current.state != state or current.message != message:
            self.monitor.events.appendleft(
                Event(
                    timestamp=time.time(),
                    node=node_id,
                    message=f"Auto recovery: {message}",
                    severity="warning"
                    if state in {"recovery_failed", "manual_intervention_required"}
                    else "info",
                )
            )
        current.state, current.message, current.checked_at = state, message, time.time()

    def ingest(self, node_id, status):
        self.states[node_id].supervisor = status
        for event in status.events:
            if event.sequence > self.seen.get(node_id, 0):
                self.monitor.events.appendleft(
                    Event(
                        timestamp=event.timestamp,
                        node=node_id,
                        message=f"Supervisor: {event.message}",
                        severity="warning"
                        if event.state
                        in {"recovery_failed", "manual_intervention_required"}
                        else "info",
                    )
                )
                self.seen[node_id] = event.sequence

    def view(self):
        nodes = []
        for node in self.monitor.nodes:
            if node.role != "worker":
                continue
            result = self.states[node.id].model_copy(deep=True)
            result.enabled = self.configuration.nodes.get(node.id, False)
            if node.agent_status == "online" and node.supervisor:
                self.ingest(node.id, node.supervisor)
                result.supervisor = node.supervisor
            elif node.agent_status != "online":
                result.supervisor = None
            if (
                not self.settings.auto_recovery_approved
                or not self.configuration.enabled
                or not result.enabled
            ):
                result.state = "disabled"
                result.message = "Automatic recovery is disabled"
            nodes.append(result)
        return RecoveryStatus(
            approved=self.settings.auto_recovery_approved,
            configuration=self.configuration,
            nodes=nodes,
            configuration_error=self.error,
        )

    async def configure(self, update: RecoveryUpdate):
        if update.enabled and not self.settings.auto_recovery_approved:
            raise HTTPException(
                403, "Server approval ARC_AUTO_RECOVERY_APPROVED is required"
            )
        if update.enabled and not update.confirmed:
            raise HTTPException(409, "Confirm automatic recovery before enabling it")
        config = RecoveryConfiguration(**update.model_dump(exclude={"confirmed"}))
        try:
            atomic_json(self.path, config.model_dump())
        except OSError:
            raise HTTPException(503, "Could not persist recovery settings") from None
        self.configuration, self.error = config, None
        # Revoke disabled nodes immediately where reachable. Offline leases expire.
        for node in self.monitor.nodes:
            if node.role == "worker" and (
                not config.enabled or not config.nodes.get(node.id)
            ):
                if node.id in self.agents.credentials:
                    with contextlib.suppress(HTTPException):
                        await self.agents.request(
                            node,
                            "PUT",
                            "/automation/policy",
                            json=self.policy(enabled=False).model_dump(),
                        )
        self.wake.set()
        return self.view()

    async def start(self):
        self.task = asyncio.create_task(self.run(), name="arc-recovery-controller")

    async def close(self):
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task

    async def run(self):
        while True:
            try:
                await self.tick()
            except Exception:
                # Keep the loop alive, but do not execute work after unknown errors.
                self.error = (
                    "Recovery reconciliation failed; no unchecked action allowed"
                )
            try:
                await asyncio.wait_for(self.wake.wait(), self.configuration.interval)
            except TimeoutError:
                pass
            self.wake.clear()

    async def tick(self):
        # Health/status events are useful even while automation is disabled.
        for node in self.monitor.nodes:
            if (
                node.role == "worker"
                and node.agent_status == "online"
                and node.supervisor
            ):
                self.ingest(node.id, node.supervisor)
        if (
            not self.settings.auto_recovery_approved
            or not self.configuration.enabled
            or self.error
        ):
            return
        dispatched = False
        for node in self.monitor.nodes:
            if node.role != "worker" or not self.configuration.nodes.get(node.id):
                continue
            if time.time() < self.next_contact.get(node.id, 0):
                continue
            try:
                # Never rely on cached reachability or process-presence observations.
                health = await self.agents.request(node, "GET", "/health")
                if (
                    type(health.get("ray_process")) is not bool
                    or "supervisor" not in health
                ):
                    self.event(
                        node.id,
                        "manual_intervention_required",
                        "Agent upgrade or complete health evidence required",
                    )
                    continue
                status = SupervisorStatus.model_validate(health["supervisor"])
                self.ingest(node.id, status)
                self.failures[node.id] = 0
                if not status.approved:
                    self.event(
                        node.id,
                        "manual_intervention_required",
                        "Worker supervisor has not been approved",
                    )
                    continue
                # Fresh, complete Ray membership is required before granting permission.
                ray = self.monitor.ray_snapshot()
                if not ray.available:
                    await self.agents.request(
                        node,
                        "PUT",
                        "/automation/policy",
                        json=self.policy(enabled=False).model_dump(),
                    )
                    self.event(
                        node.id,
                        "manual_intervention_required",
                        "Ray membership unknown; no recovery permission granted",
                    )
                    continue
                # Check again after I/O so a simultaneous disable cannot renew a lease.
                if not self.configuration.enabled or not self.configuration.nodes.get(
                    node.id
                ):
                    continue
                config = self.configuration
                policy = self.policy(
                    enabled=True,
                    interval=config.interval,
                    max_retries=config.max_retries,
                    lease_seconds=min(660, config.interval * 2 + 30),
                )
                await self.agents.request(
                    node, "PUT", "/automation/policy", json=policy.model_dump()
                )
                alive = any(n["ip"] == node.ip and n["alive"] for n in ray.nodes)
                if alive:
                    self.event(
                        node.id,
                        "healthy",
                        "Worker is a live Ray member; no restart requested",
                    )
                    continue
                if status.manual_hold or status.attempts >= config.max_retries:
                    self.event(
                        node.id,
                        "manual_intervention_required",
                        "Recovery hold or retry limit requires operator review",
                    )
                    continue
                self.event(
                    node.id,
                    "worker_disconnected"
                    if health["ray_process"]
                    else "worker_stopped",
                    "Ray process running but disconnected"
                    if health["ray_process"]
                    else "Ray worker process stopped",
                )
                if dispatched or self.control_lock.locked():
                    continue
                if status.next_attempt and time.time() < status.next_attempt:
                    self.event(node.id, status.state, "Waiting for exponential backoff")
                    continue
                async with self.control_lock:
                    if (
                        not self.configuration.enabled
                        or not self.configuration.nodes.get(node.id)
                    ):
                        continue
                    # Independent preflight checks workloads and process state.
                    safe = await self.agents.request(
                        node, "GET", "/preflight", timeout=18
                    )
                    if (
                        safe.get("verified") is not True
                        or safe.get("busy") is not False
                        or safe.get("member") is not False
                        or type(safe.get("ray_process")) is not bool
                    ):
                        self.event(
                            node.id,
                            "manual_intervention_required",
                            "Workloads active or safety state unknown",
                        )
                        continue
                    if (
                        not self.configuration.enabled
                        or not self.configuration.nodes.get(node.id)
                    ):
                        continue
                    dispatched = True
                    self.event(
                        node.id,
                        "recovering",
                        "Requesting safety-checked worker recovery",
                    )
                    self.monitor.managing.add(node.id)
                    try:
                        result = await self.agents.request(
                            node, "POST", "/automation/reconcile", timeout=120
                        )
                        status = SupervisorStatus.model_validate(result)
                        self.ingest(node.id, status)
                        self.event(node.id, status.state, status.message)
                    finally:
                        self.monitor.managing.discard(node.id)
                        self.monitor.wake.set()
            except HTTPException as exc:
                self.failures[node.id] = min(6, self.failures.get(node.id, 0) + 1)
                self.next_contact[node.id] = time.time() + min(
                    900, self.configuration.interval * 2 ** (self.failures[node.id] - 1)
                )
                state = (
                    "waiting_for_node"
                    if exc.status_code in {502, 503, 504}
                    else "manual_intervention_required"
                )
                self.event(
                    node.id,
                    state,
                    "Agent unavailable or safety check refused; no unchecked restart",
                )
            except (ValueError, KeyError, TypeError):
                self.event(
                    node.id,
                    "manual_intervention_required",
                    "Invalid agent evidence; no action allowed",
                )
