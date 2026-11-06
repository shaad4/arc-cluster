import time

from fastapi import APIRouter, HTTPException, Query, Request

from arc.models.cluster import (
    Aggregate,
    Event,
    History,
    Node,
    Overview,
    RayStatus,
    StateList,
)

router = APIRouter()


def monitor(request: Request):
    return request.app.state.monitor


def get_node(request: Request, node_id: str) -> Node:
    node = next((n for n in monitor(request).overview().nodes if n.id == node_id), None)
    if node is None:
        raise HTTPException(404, "Unknown configured node")
    return node


@router.get("/cluster/overview", response_model=Overview)
async def overview(request: Request):
    return monitor(request).overview()


@router.get("/cluster/nodes", response_model=list[Node])
async def nodes(request: Request):
    return monitor(request).overview().nodes


@router.get("/nodes/{node_id}", response_model=Node)
async def node(request: Request, node_id: str):
    return get_node(request, node_id)


@router.get("/nodes/{node_id}/metrics", response_model=Node)
async def node_metrics(request: Request, node_id: str):
    return get_node(request, node_id)


@router.get("/cluster/resources", response_model=RayStatus)
@router.get("/ray/status", response_model=RayStatus)
async def ray_status(request: Request):
    return monitor(request).ray_snapshot()


@router.get("/ray/tasks", response_model=StateList)
async def tasks(request: Request):
    return monitor(request).ray_snapshot().tasks


@router.get("/ray/actors", response_model=StateList)
async def actors(request: Request):
    return monitor(request).ray_snapshot().actors


@router.get("/cluster/events", response_model=list[Event])
async def events(request: Request):
    return list(monitor(request).events)


@router.get("/metrics/cluster", response_model=Aggregate)
async def metrics(request: Request):
    return monitor(request).aggregate()


@router.get("/metrics/history", response_model=History)
async def history(request: Request, minutes: int = Query(5, ge=1, le=60)):
    cutoff = time.time() - minutes * 60
    return History(
        samples=[s for s in monitor(request).history if s.aggregate.timestamp >= cutoff]
    )
