"""Single sampler, bounded history, explicit unknown and stale observations."""

import asyncio
import contextlib
import logging
import time
from collections import deque

from arc.collectors.local import collect_local
from arc.config import Settings
from arc.models.cluster import (
    Aggregate,
    Event,
    HistorySample,
    Metrics,
    Node,
    Overview,
    RayStatus,
)
from arc.services.bridge import RayBridge

INVENTORY = [
    ("box1", "head", "100.118.85.127"),
    ("box2", "worker", "100.124.19.50"),
    ("box3", "worker", "100.64.151.60"),
    ("box4", "worker", "100.93.80.83"),
    ("box5", "worker", "100.96.223.107"),
]


class Monitor:
    def __init__(self, settings: Settings, bridge=None, agents=None):
        self.settings = settings
        self.bridge = bridge or RayBridge(settings)
        self.agents = agents
        self.nodes = [Node(id=n, name=n, role=r, ip=ip) for n, r, ip in INVENTORY]
        self.ray = RayStatus()
        self.history = deque(maxlen=720)
        self.events = deque(maxlen=200)
        self.updated_at = None
        self.error = None
        self.task = None
        self.wake = asyncio.Event()
        self.managing: set[str] = set()

    async def start(self):
        if self.settings.collector_enabled:
            self.task = asyncio.create_task(self.run(), name="arc-sampler")

    async def close(self):
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
        await self.bridge.close()
        if self.agents:
            await self.agents.close()

    async def run(self):
        while True:
            start = time.monotonic()
            try:
                await self.sample()
            except Exception:
                self.error = "Collector failed; retrying automatically"
                logging.getLogger(__name__).exception("collector_failure")
            delay = max(0.5, self.settings.poll_interval - (time.monotonic() - start))
            try:
                await asyncio.wait_for(self.wake.wait(), delay)
            except TimeoutError:
                pass
            self.wake.clear()

    async def sample(self):
        calls = [self.bridge.call("snapshot"), asyncio.to_thread(collect_local)]
        if self.agents:
            calls.append(self.agents.collect(self.nodes))
        results = await asyncio.gather(*calls, return_exceptions=True)
        raw, local = results[:2]
        agent_data = (
            results[2] if len(results) > 2 and isinstance(results[2], dict) else {}
        )
        now = time.time()
        if isinstance(raw, Exception):
            self.ray = RayStatus(error="Ray unavailable; membership is unknown")
        else:
            self.ray = RayStatus(
                available=True,
                version=raw["version"],
                sampled_at=now,
                error=None,
                total=raw["total"],
                free=raw["available"],
                nodes=raw["nodes"],
                tasks=raw["tasks"],
                actors=raw["actors"],
            )
        for node in self.nodes:
            old_status = node.status
            members = [n for n in self.ray.nodes if n["ip"] == node.ip]
            member = next(
                (n for n in members if n["alive"]), members[-1] if members else None
            )
            node.ray_status = (
                ("alive" if member and member["alive"] else "dead")
                if self.ray.available
                else "unknown"
            )
            node.ray_id = member["id"] if member else None
            node.resources = member["resources"] if member and member["alive"] else {}
            value = (
                raw.get("metrics", {}).get(node.ray_id)
                if isinstance(raw, dict)
                else None
            )
            source = "ray" if value else None
            if node.id == self.settings.local_node and isinstance(local, dict):
                value, source = local, "local"
            agent = agent_data.get(node.id)
            if agent:
                node.agent_status = agent.get("status", "unavailable")
                node.ray_process = agent.get("ray_process")
                if agent.get("metrics"):
                    value, source = agent["metrics"], "agent"
            if value:
                metric = Metrics.model_validate(value)
                previous = node.metrics
                if (
                    previous
                    and metric.timestamp > previous.timestamp
                    and metric.uptime >= previous.uptime
                ):
                    elapsed = metric.timestamp - previous.timestamp
                    if metric.net_sent >= previous.net_sent:
                        metric.net_sent_rate = (
                            metric.net_sent - previous.net_sent
                        ) / elapsed
                    if metric.net_recv >= previous.net_recv:
                        metric.net_recv_rate = (
                            metric.net_recv - previous.net_recv
                        ) / elapsed
                node.metrics = metric
                node.last_seen = metric.timestamp
                node.source = source
            node.stale = (
                node.last_seen is None
                or now - node.last_seen > self.settings.stale_after
            )
            node.machine_status = (
                "online" if value or node.ray_status == "alive" else "unknown"
            )
            # Agent timeout does not prove that the VM is powered off.
            node.status = (
                "healthy"
                if node.ray_status == "alive" and not node.stale
                else "degraded"
                if node.machine_status == "online" or node.last_seen
                else "unknown"
            )
            if node.role == "head":
                node.control_reason = "Head node controls are disabled"
            elif node.agent_status != "online":
                node.control_reason = "Authenticated worker agent unavailable"
            else:
                node.control_reason = (
                    "Fresh safety preflight required before any action"
                )
            if node.status != old_status:
                self.events.appendleft(
                    Event(
                        timestamp=now,
                        node=node.id,
                        message=f"{node.name}: {old_status} → {node.status}",
                        severity="info" if node.status == "healthy" else "warning",
                    )
                )
        self.updated_at, self.error = now, None
        self.history.append(
            HistorySample(
                aggregate=self.aggregate(),
                nodes={
                    n.id: n.metrics.model_copy()
                    for n in self.nodes
                    if n.metrics and not n.stale
                },
            )
        )
        while self.history and now - self.history[0].aggregate.timestamp > 3600:
            self.history.popleft()

    def ray_snapshot(self):
        if (
            self.ray.sampled_at
            and time.time() - self.ray.sampled_at > self.settings.stale_after
        ):
            return RayStatus(error="Ray observations are stale; membership is unknown")
        return self.ray

    def aggregate(self):
        now = time.time()
        ray = self.ray_snapshot()
        metrics = [
            n.metrics
            for n in self.nodes
            if n.metrics and now - n.metrics.timestamp <= self.settings.stale_after
        ]
        active = (
            sum(n.ray_status == "alive" for n in self.nodes) if ray.available else None
        )
        result = Aggregate(
            timestamp=now,
            reporting_nodes=len(metrics),
            active_nodes=active,
            ray_cpu_total=ray.total.get("CPU") if ray.available else None,
            ray_cpu_available=ray.free.get("CPU", 0) if ray.available else None,
        )
        if metrics:
            cpus = sum(m.cpu_count for m in metrics)
            result.cpu_percent = (
                sum(m.cpu_percent * m.cpu_count for m in metrics) / cpus
                if cpus
                else None
            )
            result.memory_total = sum(m.memory_total for m in metrics)
            result.memory_used = sum(m.memory_used for m in metrics)
            result.memory_percent = (
                100 * result.memory_used / result.memory_total
                if result.memory_total
                else None
            )
            disk_total = sum(m.disk_total for m in metrics)
            result.disk_percent = (
                100 * sum(m.disk_used for m in metrics) / disk_total
                if disk_total
                else None
            )
            for field in ["net_sent_rate", "net_recv_rate"]:
                values = [
                    getattr(m, field) for m in metrics if getattr(m, field) is not None
                ]
                setattr(result, field, sum(values) if values else None)
        return result

    def overview(self):
        now = time.time()
        ray = self.ray_snapshot()
        nodes = [n.model_copy(deep=True) for n in self.nodes]
        for n in nodes:
            n.stale = (
                n.last_seen is None or now - n.last_seen > self.settings.stale_after
            )
            if not ray.available:
                n.ray_status = "unknown"
                if n.stale:
                    n.machine_status = "unknown"
            if not ray.available and n.status == "healthy":
                n.status = "degraded"
            if n.id in self.managing:
                n.status = "recovering"
            if n.stale and n.status == "healthy":
                n.status = "degraded"
        return Overview(
            status="healthy"
            if all(n.status == "healthy" for n in nodes)
            else "degraded",
            configured_nodes=len(nodes),
            active_nodes=self.aggregate().active_nodes,
            updated_at=self.updated_at,
            collector_error=self.error,
            aggregate=self.aggregate(),
            nodes=nodes,
            ray=ray,
            events=list(self.events),
        )
