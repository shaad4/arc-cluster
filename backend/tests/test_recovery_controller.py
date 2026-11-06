import asyncio

import httpx
import pytest
from fastapi import HTTPException

from arc.config import Settings
from arc.main import create_app
from arc.models.cluster import RayStatus
from arc.models.recovery import RecoveryConfiguration, RecoveryUpdate, SupervisorStatus
from arc.services.monitor import Monitor
from arc.services.recovery import RecoveryController


class Agents:
    credentials = {"box2": "not-a-real-token"}

    def __init__(self):
        self.calls = []
        self.healthy = False
        self.process = False
        self.busy = False
        self.verified = True
        self.unreachable = False

    async def request(self, node, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if self.unreachable:
            raise HTTPException(503, "unreachable")
        if path == "/health":
            return {
                "ray_process": self.process,
                "supervisor": SupervisorStatus(approved=True).model_dump(),
            }
        if path == "/preflight":
            return {
                "verified": self.verified,
                "busy": self.busy,
                "member": self.healthy,
                "ray_process": self.process,
            }
        if path == "/automation/reconcile":
            return SupervisorStatus(
                approved=True,
                state="recovery_successful",
                last_result="recovery_successful",
            ).model_dump()
        return SupervisorStatus(approved=True).model_dump()


def controller(tmp_path):
    settings = Settings(
        auto_recovery_approved=True,
        auto_recovery_file=str(tmp_path / "config.json"),
        collector_enabled=False,
    )
    monitor = Monitor(settings)
    monitor.ray = RayStatus(available=True, error=None, nodes=[])
    agents = Agents()
    result = RecoveryController(settings, monitor, agents, asyncio.Lock())
    result.configuration = RecoveryConfiguration(enabled=True, nodes={"box2": True})
    return result, agents


def test_stopped_and_disconnected_worker_recovery(tmp_path):
    for process in [False, True]:
        recovery, agents = controller(tmp_path)
        agents.process = process
        asyncio.run(recovery.tick())
        assert ("POST", "/automation/reconcile") in [(m, p) for m, p, _ in agents.calls]
        assert recovery.states["box2"].state == "recovery_successful"
        assert recovery.monitor.events
        assert not recovery.monitor.managing


@pytest.mark.parametrize(
    "case",
    [
        "healthy",
        "unreachable",
        "busy",
        "unknown",
        "ray_unavailable",
        "disabled",
        "unapproved",
    ],
)
def test_no_unsafe_action(tmp_path, case):
    recovery, agents = controller(tmp_path)
    if case == "healthy":
        recovery.monitor.ray.nodes = [{"ip": "100.124.19.50", "alive": True}]
    elif case == "unreachable":
        agents.unreachable = True
    elif case == "busy":
        agents.busy = True
    elif case == "unknown":
        agents.verified = False
    elif case == "ray_unavailable":
        recovery.monitor.ray.available = False
    elif case == "disabled":
        recovery.configuration.enabled = False
    elif case == "unapproved":
        recovery.settings.auto_recovery_approved = False
    asyncio.run(recovery.tick())
    assert not any(path == "/automation/reconcile" for _, path, _ in agents.calls)


def test_configuration_requires_approval_and_persists(tmp_path):
    recovery, _ = controller(tmp_path)

    async def check():
        with pytest.raises(HTTPException):
            await recovery.configure(RecoveryUpdate(enabled=True, confirmed=False))
        await recovery.configure(
            RecoveryUpdate(enabled=True, confirmed=True, nodes={"box2": True})
        )
        restored = RecoveryController(
            recovery.settings, recovery.monitor, recovery.agents, asyncio.Lock()
        )
        assert restored.configuration.enabled and restored.configuration.nodes["box2"]
        recovery.settings.auto_recovery_approved = False
        with pytest.raises(HTTPException):
            await recovery.configure(RecoveryUpdate(enabled=True, confirmed=True))

    asyncio.run(check())


def test_recovery_api_disabled_by_default(tmp_path):
    async def check():
        app = create_app(
            Settings(
                collector_enabled=False, auto_recovery_file=str(tmp_path / "empty.json")
            )
        )
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://localhost"
            ) as client:
                response = await client.get("/api/recovery")
                assert not response.json()["approved"]
                assert not response.json()["configuration"]["enabled"]
                response = await client.patch(
                    "/api/recovery",
                    headers={"Origin": "http://localhost", "X-ARC-Request": "1"},
                    json={"enabled": True, "confirmed": True},
                )
                assert response.status_code == 403

    asyncio.run(check())
