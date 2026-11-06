from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from arc.config import APP_VERSION
from arc.models.cluster import Node

router = APIRouter()


class SettingsResponse(BaseModel):
    name: str = "ARC"
    version: str = APP_VERSION
    head_address: str
    ray_version: str | None
    poll_interval: int
    collector_status: str
    application_health: str = "ok"
    nodes: list[Node]
    approved_workload: bool


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    poll_interval: int = Field(ge=5, le=60, strict=True)


@router.get("/settings", response_model=SettingsResponse)
async def settings(request: Request):
    config = request.app.state.settings
    monitor = request.app.state.monitor
    return SettingsResponse(
        head_address=config.ray_address,
        ray_version=monitor.ray.version,
        poll_interval=config.poll_interval,
        collector_status="disabled"
        if not config.collector_enabled
        else "error"
        if monitor.error
        else "running"
        if monitor.updated_at
        else "starting",
        nodes=monitor.overview().nodes,
        approved_workload=config.approved_workload,
    )


@router.patch("/settings", response_model=SettingsResponse)
async def update(request: Request, body: SettingsUpdate):
    request.app.state.settings.poll_interval = body.poll_interval
    request.app.state.monitor.wake.set()
    return await settings(request)
