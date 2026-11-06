from typing import Any, Literal

from pydantic import BaseModel, Field


class Metrics(BaseModel):
    timestamp: float
    hostname: str
    cpu_percent: float
    cpu_count: int
    memory_total: int
    memory_used: int
    memory_percent: float
    disk_total: int
    disk_used: int
    disk_percent: float
    net_sent: int
    net_recv: int
    uptime: float
    net_sent_rate: float | None = None
    net_recv_rate: float | None = None


class Node(BaseModel):
    id: str
    name: str
    role: Literal["head", "worker"]
    ip: str
    machine_status: Literal["online", "unknown", "unreachable"] = "unknown"
    ray_status: Literal["alive", "dead", "unknown"] = "unknown"
    status: Literal["healthy", "degraded", "offline", "unknown", "recovering"] = (
        "unknown"
    )
    ray_id: str | None = None
    resources: dict[str, float] = Field(default_factory=dict)
    metrics: Metrics | None = None
    last_seen: float | None = None
    stale: bool = True
    source: str | None = None
    agent_status: str = "not configured"
    ray_process: bool | None = None
    control_reason: str = "Agent credentials and safety checks required"


class StateList(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class RayStatus(BaseModel):
    available: bool = False
    version: str | None = None
    sampled_at: float | None = None
    error: str | None = "Waiting for the first Ray sample"
    total: dict[str, float] = Field(default_factory=dict)
    free: dict[str, float] = Field(default_factory=dict)
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    tasks: StateList = Field(default_factory=lambda: StateList(error="Not sampled"))
    actors: StateList = Field(default_factory=lambda: StateList(error="Not sampled"))


class Aggregate(BaseModel):
    timestamp: float
    cpu_percent: float | None = None
    memory_percent: float | None = None
    memory_used: int | None = None
    memory_total: int | None = None
    disk_percent: float | None = None
    net_sent_rate: float | None = None
    net_recv_rate: float | None = None
    reporting_nodes: int = 0
    active_nodes: int | None = None
    ray_cpu_total: float | None = None
    ray_cpu_available: float | None = None


class Event(BaseModel):
    timestamp: float
    node: str | None = None
    message: str
    severity: str = "info"


class Overview(BaseModel):
    status: str
    configured_nodes: int
    active_nodes: int | None
    updated_at: float | None
    collector_error: str | None
    aggregate: Aggregate
    nodes: list[Node]
    ray: RayStatus
    events: list[Event]


class HistorySample(BaseModel):
    aggregate: Aggregate
    nodes: dict[str, Metrics]


class History(BaseModel):
    samples: list[HistorySample]
    retention_seconds: int = 3600
