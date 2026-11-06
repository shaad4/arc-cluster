import asyncio
from contextlib import nullcontext

import pytest

from arc.agent.supervisor import RecoveryBlocked, Supervisor
from arc.models.recovery import AgentPolicy, WorkerObservation


class Operations:
    def __init__(self):
        self.value = WorkerObservation(
            tailscale_ip="100.124.19.50",
            member=False,
            ray_process=False,
            verified=True,
            busy=False,
        )
        self.calls = []
        self.success = True
        self.block = None

    def guard(self):
        return nullcontext()

    async def observe(self):
        if self.block:
            raise self.block
        return self.value

    async def change(self, action, ip, authorized):
        assert authorized()
        self.calls.append((action, ip))

    async def verify(self, ip):
        return self.success


def engine(tmp_path, ops):
    worker = Supervisor(ops, tmp_path / "recovery.json", approved=True)
    worker.configure(AgentPolicy(enabled=True, interval=10))
    return worker


@pytest.mark.parametrize(
    "running,member,allow,expected",
    [
        (False, False, False, "start"),
        (True, True, True, None),
        (True, False, False, None),
        (True, False, True, "recover"),
    ],
)
def test_worker_classification(tmp_path, running, member, allow, expected):
    ops = Operations()
    ops.value.ray_process, ops.value.member = running, member
    worker = engine(tmp_path, ops)
    result = asyncio.run(worker.tick(allow))
    assert [c[0] for c in ops.calls] == ([expected] if expected else [])
    if expected:
        assert result.state == "recovery_successful"
        assert result.last_attempt is not None


@pytest.mark.parametrize("verified,busy", [(False, False), (True, True)])
def test_incomplete_or_active_workloads_refused(tmp_path, verified, busy):
    ops = Operations()
    ops.value.verified, ops.value.busy = verified, busy
    worker = engine(tmp_path, ops)
    assert asyncio.run(worker.tick(True)).state == "manual_intervention_required"
    assert not ops.calls


@pytest.mark.parametrize("reason", ["Head unavailable", "Tailscale unavailable"])
def test_network_failures_do_not_consume_attempts(tmp_path, reason):
    ops = Operations()
    ops.block = RecoveryBlocked("waiting_for_node", reason)
    worker = engine(tmp_path, ops)
    result = asyncio.run(worker.tick(True))
    assert result.state == "waiting_for_node" and result.attempts == 0
    assert not ops.calls


def test_retry_backoff_survives_restart_and_exhausts(tmp_path):
    ops = Operations()
    ops.success = False
    worker = engine(tmp_path, ops)
    clock = [1000.0]
    worker.clock = lambda: clock[0]
    asyncio.run(worker.tick())
    assert worker.status.next_attempt == 1010
    asyncio.run(worker.tick())
    assert len(ops.calls) == 1
    # A new agent process must preserve the durable budget; it needs a new lease.
    worker = Supervisor(ops, worker.path, approved=True, clock=lambda: clock[0])
    assert not worker.snapshot().enabled
    worker.configure(AgentPolicy(enabled=True, interval=10, max_retries=2))
    clock[0] = 1011
    result = asyncio.run(worker.tick())
    assert result.attempts == 2 and result.state == "manual_intervention_required"
    clock[0] = 9999
    asyncio.run(worker.tick(True))
    assert len(ops.calls) == 2


def test_default_disabled_expired_lease_and_manual_hold(tmp_path):
    ops = Operations()
    worker = Supervisor(ops, tmp_path / "ledger.json", approved=True)
    asyncio.run(worker.tick())
    assert not ops.calls
    worker.configure(AgentPolicy(enabled=True))
    worker.lease_deadline = 0
    asyncio.run(worker.tick())
    assert not ops.calls
    worker.configure(AgentPolicy(enabled=True))
    worker.hold()
    asyncio.run(worker.tick(True))
    assert not ops.calls
    worker.reset()
    asyncio.run(worker.tick())
    assert len(ops.calls) == 1
