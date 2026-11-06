"""Shared bounded recovery state machine. Never dispatches arbitrary commands."""

import asyncio
import json
import os
import time
from pathlib import Path

from arc.models.recovery import AgentPolicy, RecoveryEvent, SupervisorStatus


class RecoveryBlocked(Exception):
    def __init__(self, state: str, message: str):
        super().__init__(message)
        self.state, self.message = state, message


def atomic_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


class Supervisor:
    def __init__(self, operations, path: Path, approved=False, clock=time.time):
        self.operations, self.path, self.clock = operations, path, clock
        self.policy = AgentPolicy()
        self.status = SupervisorStatus(approved=approved)
        self.lease_deadline = 0.0
        self.stable_since = None
        self.lock = asyncio.Lock()
        self.storage_error = False
        if path.exists():
            try:
                old = SupervisorStatus.model_validate_json(path.read_text())
                old.approved, old.enabled, old.lease_expires = approved, False, None
                self.status = old
            except (OSError, ValueError):
                self.storage_error = True
                self.status.state = "manual_intervention_required"
                self.status.message = "Recovery ledger unreadable; inspect it manually"

    def save(self):
        try:
            atomic_json(self.path, self.status.model_dump())
        except OSError as exc:
            self.storage_error = True
            raise RecoveryBlocked(
                "manual_intervention_required", "Cannot persist recovery budget"
            ) from exc

    def transition(self, state, message):
        if self.status.state != state or self.status.message != message:
            sequence = self.status.events[-1].sequence + 1 if self.status.events else 1
            self.status.events.append(
                RecoveryEvent(
                    sequence=sequence,
                    timestamp=self.clock(),
                    state=state,
                    message=message,
                )
            )
            self.status.events = self.status.events[-30:]
        self.status.state, self.status.message = state, message
        self.save()

    def lease_valid(self):
        return (
            self.status.approved
            and self.policy.enabled
            and time.monotonic() < self.lease_deadline
        )

    def configure(self, policy: AgentPolicy):
        if self.storage_error:
            raise RecoveryBlocked(
                "manual_intervention_required",
                "Inspect recovery ledger before configuring",
            )
        self.policy = policy
        self.lease_deadline = (
            time.monotonic() + policy.lease_seconds if policy.enabled else 0
        )
        self.status.enabled = policy.enabled and self.status.approved
        self.status.lease_expires = (
            self.clock() + policy.lease_seconds if self.status.enabled else None
        )
        # Changing policy does not reset attempts or an intentional-stop hold.
        if not self.status.enabled:
            self.transition("disabled", "Automatic recovery is disabled")
        return self.snapshot()

    def snapshot(self):
        result = self.status.model_copy(deep=True)
        result.enabled = self.lease_valid()
        if self.status.approved and self.policy.enabled and not result.enabled:
            result.state, result.message = (
                "disabled",
                "Controller permission lease expired",
            )
        return result

    def reset(self):
        if self.lock.locked():
            raise RecoveryBlocked("recovering", "Operation is still in progress")
        if self.storage_error:
            raise RecoveryBlocked(
                "manual_intervention_required", "Inspect the recovery ledger first"
            )
        self.status.attempts = 0
        self.status.next_attempt = None
        self.status.manual_hold = False
        self.transition("disabled", "Budget reset by operator; awaiting reconciliation")
        return self.snapshot()

    def hold(self):
        self.status.manual_hold = True
        self.transition(
            "manual_intervention_required",
            "Intentional stop; reset automation hold to resume",
        )

    async def tick(self, allow_restart=False):
        if not self.lease_valid() or self.lock.locked():
            return self.snapshot()
        async with self.lock:
            attempted = False
            try:
                if self.storage_error or self.status.manual_hold:
                    return self.snapshot()
                # Shared cross-process lock also covers manual management.
                with self.operations.guard():
                    observed = await self.operations.observe()
                    if observed.member:
                        if not observed.ray_process:
                            raise RecoveryBlocked(
                                "manual_intervention_required",
                                "Membership and process observations disagree",
                            )
                        self.stable_since = self.stable_since or self.clock()
                        if self.clock() - self.stable_since >= 300:
                            self.status.attempts = 0
                            self.status.next_attempt = None
                        self.transition("healthy", "Worker is a live Ray member")
                        return self.snapshot()
                    self.stable_since = None
                    if not observed.verified or observed.busy:
                        raise RecoveryBlocked(
                            "manual_intervention_required",
                            "Workload state unknown or active workloads present",
                        )
                    if observed.ray_process and not allow_restart:
                        self.transition(
                            "worker_disconnected",
                            "Running process disconnected; controller review required",
                        )
                        return self.snapshot()
                    if self.status.attempts >= self.policy.max_retries:
                        raise RecoveryBlocked(
                            "manual_intervention_required",
                            "Retry limit exceeded; operator reset required",
                        )
                    if (
                        self.status.next_attempt
                        and self.clock() < self.status.next_attempt
                    ):
                        return self.snapshot()
                    if not self.lease_valid():
                        return self.snapshot()
                    action = "recover" if observed.ray_process else "start"
                    if action == "start":
                        self.transition(
                            "worker_stopped", "Ray worker process is absent"
                        )
                    # Persist before touching Ray; restart must not reset the budget.
                    attempted = True
                    self.status.attempts += 1
                    self.status.last_attempt = self.clock()
                    delay = min(
                        1800, self.policy.interval * 2 ** (self.status.attempts - 1)
                    )
                    # Stable per-node staggering prevents synchronized retries.
                    stagger = int(observed.tailscale_ip.split(".")[-1]) % 10
                    self.status.next_attempt = self.clock() + delay + stagger
                    self.transition(
                        "recovering", f"Attempt {self.status.attempts}: {action}"
                    )
                    await self.operations.change(
                        action, observed.tailscale_ip, self.lease_valid
                    )
                    if not await self.operations.verify(observed.tailscale_ip):
                        raise RuntimeError("Membership verification failed")
                    self.status.last_result = "recovery_successful"
                    self.transition(
                        "recovery_successful", "Fresh Ray membership verified"
                    )
                    # Counters reset only after five continuous minutes of health.
                    self.stable_since = self.clock()
            except RecoveryBlocked as exc:
                if attempted:
                    self.status.last_result = "recovery_failed"
                self.stable_since = None
                try:
                    self.transition(exc.state, exc.message)
                except RecoveryBlocked:
                    self.status.state = "manual_intervention_required"
            except asyncio.CancelledError:
                self.status.last_result = "recovery_failed"
                self.transition(
                    "recovery_failed", "Operation interrupted; inspect worker state"
                )
                raise
            except Exception:
                self.status.last_result = "recovery_failed"
                state = (
                    "manual_intervention_required"
                    if self.status.attempts >= self.policy.max_retries
                    else "recovery_failed"
                )
                self.transition(
                    state, "Recovery failed; retry budget and backoff apply"
                )
        return self.snapshot()
