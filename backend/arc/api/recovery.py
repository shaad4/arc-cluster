from fastapi import APIRouter, HTTPException, Request

from arc.api.cluster import get_node
from arc.api.controls import Confirmation
from arc.models.recovery import RecoveryStatus, RecoveryUpdate, SupervisorStatus

router = APIRouter()


@router.get("/recovery", response_model=RecoveryStatus)
async def status(request: Request):
    return request.app.state.recovery.view()


@router.patch("/recovery", response_model=RecoveryStatus)
async def configure(request: Request, body: RecoveryUpdate):
    return await request.app.state.recovery.configure(body)


@router.post("/recovery/{node_id}/reset", response_model=SupervisorStatus)
async def reset(request: Request, node_id: str, body: Confirmation):
    node = get_node(request, node_id)
    if node.role != "worker" or not body.confirmed:
        raise HTTPException(409, "Explicit worker budget-reset confirmation required")
    if request.app.state.control_lock.locked():
        raise HTTPException(409, "A management operation is active")
    async with request.app.state.control_lock:
        result = await request.app.state.agents.request(
            node, "POST", "/automation/reset"
        )
    request.app.state.recovery.wake.set()
    return SupervisorStatus.model_validate(result)
