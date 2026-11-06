import asyncio

import pytest

from arc.agent import operations
from arc.agent.operations import WorkerOperations
from arc.agent.supervisor import RecoveryBlocked
from arc.models.recovery import WorkerObservation


def test_actual_tailscale_identity_required(tmp_path, monkeypatch):
    monkeypatch.setenv("ARC_AGENT_BIND", "100.124.19.50")

    async def execute(*args, **kwargs):
        return b'{"BackendState":"Running","TailscaleIPs":["100.124.19.50"]}'

    monkeypatch.setattr(operations, "execute", execute)
    worker = WorkerOperations(tmp_path)
    assert asyncio.run(worker.identity()) == "100.124.19.50"
    monkeypatch.setenv("ARC_AGENT_BIND", "100.64.151.60")
    with pytest.raises(RecoveryBlocked):
        asyncio.run(worker.identity())


def test_head_unreachable(tmp_path, monkeypatch):
    async def connect(*args, **kwargs):
        raise OSError("head unavailable")

    monkeypatch.setattr(asyncio, "open_connection", connect)
    with pytest.raises(RecoveryBlocked, match="Head unreachable"):
        asyncio.run(WorkerOperations(tmp_path).head_reachable("100.124.19.50"))


@pytest.mark.parametrize(
    "busy,member,process,expected",
    [
        (False, False, False, True),
        (True, False, False, False),
        (False, True, True, False),
        (False, False, True, False),
    ],
)
def test_start_rechecks_and_never_duplicates(
    tmp_path, monkeypatch, busy, member, process, expected
):
    worker = WorkerOperations(tmp_path)
    monkeypatch.setenv("ARC_AGENT_ENABLE_CONTROLS", "1")

    async def observe():
        return WorkerObservation(
            tailscale_ip="100.124.19.50",
            verified=True,
            busy=busy,
            member=member,
            ray_process=process,
        )

    worker.observe = observe
    monkeypatch.setattr(operations, "ray_process", lambda: process)
    calls = []

    async def execute(*args, **kwargs):
        calls.append(args)

    monkeypatch.setattr(operations, "execute", execute)

    async def check():
        if expected:
            await worker.change("start", "100.124.19.50")
        else:
            with pytest.raises(RecoveryBlocked):
                await worker.change("start", "100.124.19.50")

    asyncio.run(check())
    assert bool(calls) == expected
    if expected:
        assert calls[0] == (
            "/data/cluster/venv/bin/ray",
            "start",
            "--address=100.118.85.127:6379",
            "--node-ip-address=100.124.19.50",
        )


def test_cross_process_operation_lock(tmp_path):
    worker = WorkerOperations(tmp_path)
    with worker.guard():
        with pytest.raises(RecoveryBlocked):
            with WorkerOperations(tmp_path).guard():
                pass


def test_unknown_state_does_not_pass(tmp_path, monkeypatch):
    monkeypatch.setenv("ARC_AGENT_STATE_URL", "http://127.0.0.1:18265")

    async def execute(*args, **kwargs):
        return b'{"verified":true,"member":false}'

    monkeypatch.setattr(operations, "execute", execute)
    with pytest.raises(RecoveryBlocked):
        asyncio.run(WorkerOperations(tmp_path).state())
