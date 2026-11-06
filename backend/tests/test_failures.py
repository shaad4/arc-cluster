import asyncio
import time

import httpx
import pytest
from fastapi import HTTPException
from test_monitor import FakeBridge

from arc.config import Settings
from arc.services.agents import AgentClient
from arc.services.bridge import BridgeUnavailable, RayBridge
from arc.services.jobs import JobService
from arc.services.monitor import Monitor


def test_missing_ray_interpreter_does_not_break_api():
    async def check():
        bridge = RayBridge(Settings(ray_python="/not/a/ray/python"))
        with pytest.raises(BridgeUnavailable):
            await bridge.call("snapshot")
        assert bridge.process is None

    asyncio.run(check())


def test_bridge_timeout_cleans_up_owned_process(tmp_path):
    # A temporary executable simulates a wedged bridge without touching Ray.
    executable = tmp_path / "blocked-bridge"
    executable.write_text("#!/usr/bin/python3\nimport time\ntime.sleep(60)\n")
    executable.chmod(0o700)

    async def check():
        bridge = RayBridge(Settings(ray_python=str(executable), bridge_timeout=2))
        start = time.monotonic()
        with pytest.raises(BridgeUnavailable):
            await bridge.call("snapshot")
        assert time.monotonic() - start < 6
        assert bridge.process is None

    asyncio.run(check())


def test_agent_timeout_is_not_machine_offline():
    async def check():
        agents = AgentClient(Settings())
        agents.credentials = {"box2": "x" * 40}
        await agents.client.aclose()

        def fail(request):
            raise httpx.ReadTimeout("unavailable")

        agents.client = httpx.AsyncClient(transport=httpx.MockTransport(fail))
        monitor = Monitor(Settings(), FakeBridge(), agents)
        await monitor.sample()
        assert monitor.nodes[1].agent_status == "unavailable"
        assert monitor.nodes[1].machine_status == "unknown"
        assert monitor.nodes[1].metrics is None
        await monitor.close()

    asyncio.run(check())


def test_job_cache_and_network_failure():
    async def check():
        calls = []

        def respond(request):
            calls.append(request)
            return httpx.Response(
                200, json=[{"job_id": "abc", "status": "RUNNING", "metadata": None}]
            )

        service = JobService(Settings())
        await service.client.aclose()
        service.client = httpx.AsyncClient(
            transport=httpx.MockTransport(respond), base_url="http://ray"
        )
        one, two = await asyncio.gather(service.list(), service.list())
        assert len(calls) == 1
        assert one == two
        assert one.items[0].id == "abc"
        await service.close()

        def fail(request):
            raise httpx.ConnectError("not reachable")

        service = JobService(Settings())
        await service.client.aclose()
        service.client = httpx.AsyncClient(
            transport=httpx.MockTransport(fail), base_url="http://ray"
        )
        with pytest.raises(HTTPException) as exc:
            await service.list()
        assert exc.value.status_code == 503
        await service.close()

    asyncio.run(check())
