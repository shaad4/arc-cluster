import asyncio
import time
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from arc.api.cluster import get_node
from arc.models.cluster import Event

router = APIRouter()


class Confirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: bool


class ControlResult(BaseModel):
    status: str
    message: str


class Preflight(BaseModel):
    allowed: bool
    reason: str
    member: bool | None = None
    ray_process: bool | None = None


@router.get("/nodes/{node_id}/preflight", response_model=Preflight)
async def preflight(request: Request, node_id: str):
    node = get_node(request, node_id)
    if node.role == "head":
        return Preflight(allowed=False, reason="Head controls disabled")
    try:
        state = await request.app.state.agents.request(
            node, "GET", "/preflight", timeout=18
        )
        return Preflight(
            allowed=state["verified"] and not state["busy"],
            reason="No active workloads; agent will recheck before execution",
            member=state["member"],
            ray_process=state["ray_process"],
        )
    except HTTPException as exc:
        return Preflight(allowed=False, reason=exc.detail)


async def control(request, node_id, action, body):
    node = get_node(request, node_id)
    if not body.confirmed:
        raise HTTPException(409, "Explicit confirmation required")
    if node.role == "head":
        raise HTTPException(403, "Head controls disabled")
    lock = request.app.state.control_lock
    if lock.locked():
        raise HTTPException(409, "Another management action is running")
    async with lock:
        check = await preflight(request, node_id)
        if not check.allowed:
            raise HTTPException(409, check.reason)
        if action in {"start", "recover"} and check.member:
            raise HTTPException(409, "Healthy Ray members must not be restarted")
        monitor = request.app.state.monitor
        monitor.events.appendleft(
            Event(
                timestamp=time.time(),
                node=node.id,
                message=f"{action} requested",
                severity="warning",
            )
        )
        await request.app.state.agents.request(
            node,
            "POST",
            "/control",
            timeout=60,
            json={"action": action, "confirmed": True},
        )
        monitor.wake.set()
        for _ in range(20):
            await asyncio.sleep(1)
            current = next(n for n in monitor.nodes if n.id == node_id)
            if monitor.ray.available and (
                (action == "stop" and current.ray_status == "dead")
                or (action != "stop" and current.ray_status == "alive")
            ):
                monitor.events.appendleft(
                    Event(
                        timestamp=time.time(),
                        node=node.id,
                        message=f"{action} verified through Ray membership",
                    )
                )
                return ControlResult(
                    status="verified", message="Ray membership verified"
                )
        return ControlResult(
            status="unverified",
            message=(
                "Command ran; membership verification timed out. "
                "Inspect node before retrying."
            ),
        )


@router.post("/nodes/{node_id}/ray/{action}", response_model=ControlResult)
async def worker_action(
    request: Request, node_id: str, action: Literal["start", "stop"], body: Confirmation
):
    return await control(request, node_id, action, body)


@router.post("/nodes/{node_id}/recover", response_model=ControlResult)
async def recover(request: Request, node_id: str, body: Confirmation):
    return await control(request, node_id, "recover", body)


@router.post("/nodes/{node_id}/refresh", response_model=ControlResult)
async def refresh(request: Request, node_id: str):
    get_node(request, node_id)
    request.app.state.monitor.wake.set()
    return ControlResult(status="queued", message="Central collector refresh requested")
