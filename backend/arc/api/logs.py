import asyncio
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request

from arc.api.cluster import get_node
from arc.services.jobs import LogResponse
from arc.services.logs import local_tail, redact

router = APIRouter()


@router.get("/logs", response_model=LogResponse)
async def logs(
    request: Request,
    node_id: str = "box1",
    source: Literal["raylet", "raylet-error", "events"] = "raylet",
    search: str = Query("", max_length=200),
    severity: Literal["all", "error", "warning", "info"] = "all",
):
    node = get_node(request, node_id)
    if source == "events":
        text = "\n".join(
            f"{e.timestamp:.0f} {e.severity} {e.message}"
            for e in request.app.state.monitor.events
            if not e.node or e.node == node_id
        )
    elif node_id == request.app.state.settings.local_node:
        try:
            text = await asyncio.to_thread(local_tail, source)
        except OSError:
            raise HTTPException(404, "Log source unavailable") from None
    else:
        data = await request.app.state.agents.request(
            node, "GET", "/logs", params={"source": source}
        )
        text = redact(data["text"])
    lines = [line for line in text.splitlines() if search.lower() in line.lower()]
    if severity != "all":
        lines = [line for line in lines if severity in line.lower()]
    return LogResponse(text="\n".join(lines)[-65536:], source=source)


@router.get("/nodes/{node_id}/logs", response_model=LogResponse)
async def node_logs(
    request: Request, node_id: str, source: Literal["raylet", "raylet-error"] = "raylet"
):
    return await logs(request, node_id, source, "", "all")
