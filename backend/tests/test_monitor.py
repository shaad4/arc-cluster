import asyncio
import time

from httpx import ASGITransport, AsyncClient

from arc.config import Settings
from arc.main import create_app
from arc.models.cluster import Metrics
from arc.services.monitor import Monitor


class FakeBridge:
    def __init__(self, fails=False):
        self.fails = fails

    async def call(self, op):
        if self.fails:
            raise TimeoutError()
        return dict(
            version="2.60.0",
            nodes=[
                dict(id="old", ip="100.118.85.127", alive=False, resources={}),
                dict(id="live", ip="100.118.85.127", alive=True, resources={"CPU": 4}),
            ],
            total={"CPU": 4},
            available={"CPU": 2},
            metrics={},
            tasks={"items": [], "error": None},
            actors={"items": [], "error": None},
        )

    async def close(self):
        pass


def test_inventory_membership_and_failure():
    async def check():
        settings = Settings(collector_enabled=False)
        bridge = FakeBridge()
        monitor = Monitor(settings, bridge)
        await monitor.sample()
        assert len(monitor.nodes) == 5
        assert monitor.nodes[0].ray_id == "live"
        assert monitor.nodes[1].ray_status == "dead"
        assert monitor.nodes[1].machine_status == "unknown"
        assert monitor.aggregate().ray_cpu_total == 4
        assert monitor.aggregate().reporting_nodes == 1
        assert len(monitor.history) == 1
        bridge.fails = True
        await monitor.sample()
        assert not monitor.ray.available
        assert monitor.nodes[0].machine_status == "online"
        assert monitor.nodes[0].ray_status == "unknown"
        assert monitor.aggregate().ray_cpu_total is None
        app = create_app(settings, monitor)
        async with AsyncClient(
            transport=ASGITransport(app), base_url="http://localhost"
        ) as client:
            assert (await client.get("/api/cluster/overview")).status_code == 200
            assert (await client.get("/api/nodes/nope")).status_code == 404
            assert (
                await client.get("/api/metrics/history?minutes=61")
            ).status_code == 422

    asyncio.run(check())


def test_stale_metrics_excluded():
    monitor = Monitor(Settings(collector_enabled=False))
    node = monitor.nodes[0]
    node.metrics = Metrics(
        timestamp=time.time() - 100,
        hostname="test",
        cpu_percent=0,
        cpu_count=4,
        memory_total=100,
        memory_used=0,
        memory_percent=0,
        disk_total=100,
        disk_used=0,
        disk_percent=0,
        net_sent=0,
        net_recv=0,
        uptime=10,
    )
    node.last_seen = node.metrics.timestamp
    node.status = "healthy"
    assert monitor.aggregate().cpu_percent is None
    assert monitor.overview().nodes[0].stale
    assert monitor.overview().nodes[0].status == "degraded"
