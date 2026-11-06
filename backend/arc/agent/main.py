"""Optional non-root Tailscale-only worker agent, separate from dashboard auth."""

import asyncio
import contextlib
import hmac
import ipaddress
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from arc.agent.operations import WorkerOperations, ray_process
from arc.agent.supervisor import RecoveryBlocked, Supervisor
from arc.collectors.local import collect_local
from arc.models.recovery import AgentPolicy, SupervisorStatus
from arc.services.agents import read_credentials
from arc.services.logs import local_tail


def recovery_directory():
    return Path(
        os.environ.get(
            "ARC_AGENT_RECOVERY_DIR", str(Path.home() / ".local/state/arc-worker")
        )
    )


def create_supervisor():
    directory = recovery_directory()
    return Supervisor(
        WorkerOperations(directory),
        directory / "recovery.json",
        approved=os.environ.get("ARC_AGENT_SUPERVISOR_APPROVED") == "1",
    )


@asynccontextmanager
async def lifespan(application):
    application.state.supervisor = create_supervisor()

    async def supervise():
        # Short local cadence; leases and per-worker backoff bound actual operations.
        while True:
            try:
                await application.state.supervisor.tick(allow_restart=False)
            except Exception:
                # Storage/observation failures must never trigger a restart.
                pass
            await asyncio.sleep(10)

    task = asyncio.create_task(supervise(), name="arc-worker-supervisor")
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title="ARC worker agent",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)
lock = asyncio.Lock()


def supervisor():
    if not hasattr(app.state, "supervisor"):
        app.state.supervisor = create_supervisor()
    return app.state.supervisor


@app.middleware("http")
async def authenticate(request: Request, call_next):
    from fastapi.responses import JSONResponse

    token = os.environ.get("ARC_AGENT_TOKEN_FILE", "")
    try:
        expected = read_credentials(token).get("token", "")
    except (OSError, ValueError):
        expected = ""
    actual = request.headers.get("authorization", "")
    if not expected or not hmac.compare_digest(actual, f"Bearer {expected}"):
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    # Explicit peer allowlist complements the Tailscale ACL.
    if request.client.host != os.environ.get("ARC_AGENT_CONTROLLER", "100.118.85.127"):
        return JSONResponse({"detail": "Controller not allowed"}, status_code=403)
    return await call_next(request)


@app.get("/health")
async def health():
    return {
        "metrics": await asyncio.to_thread(collect_local),
        "ray_process": await asyncio.to_thread(ray_process),
        "supervisor": supervisor().snapshot().model_dump(),
    }


@app.get("/logs")
async def logs(source: Literal["raylet", "raylet-error"] = "raylet"):
    try:
        return {
            "text": await asyncio.to_thread(local_tail, source),
            "source": source,
            "truncated": True,
        }
    except OSError:
        raise HTTPException(404, "Log source unavailable") from None


async def preflight():
    if os.environ.get("ARC_AGENT_BIND") == "100.118.85.127":
        raise HTTPException(403, "Head controls disabled")
    if os.environ.get("ARC_AGENT_ENABLE_CONTROLS") != "1":
        raise HTTPException(403, "Agent controls disabled in configuration")
    if not os.environ.get("ARC_AGENT_STATE_URL"):
        raise HTTPException(409, "Independent State API access is not configured")
    try:
        state = await supervisor().operations.observe()
        if state.busy or not state.verified:
            raise HTTPException(409, "Workloads active or safety state incomplete")
        return state.model_dump()
    except RecoveryBlocked as exc:
        raise HTTPException(409, exc.message) from None


@app.get("/preflight")
async def check():
    return await preflight()


class Control(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["start", "stop", "recover"]
    confirmed: bool


@app.post("/control")
async def control(body: Control):
    if not body.confirmed:
        raise HTTPException(409, "Explicit confirmation required")
    if lock.locked():
        raise HTTPException(409, "Another control operation is in progress")
    async with lock:
        state = await preflight()
        if body.action in {"start", "recover"} and state["member"]:
            raise HTTPException(409, "Worker is already a live Ray member")
        if body.action == "start" and state["ray_process"]:
            raise HTTPException(409, "Ray process already exists; inspect recovery")
        engine = supervisor()
        try:
            with engine.operations.guard():
                if body.action == "stop":
                    engine.hold()
                await engine.operations.change(
                    body.action, os.environ["ARC_AGENT_BIND"]
                )
        except RecoveryBlocked as exc:
            raise HTTPException(409, exc.message) from None
        except (OSError, ValueError, TimeoutError):
            raise HTTPException(
                502, "Allowlisted command failed; inspect worker"
            ) from None
        return {"executed": True, "action": body.action}


@app.put("/automation/policy", response_model=SupervisorStatus)
async def automation_policy(policy: AgentPolicy):
    return supervisor().configure(policy)


@app.post("/automation/reconcile", response_model=SupervisorStatus)
async def automation_reconcile():
    return await supervisor().tick(allow_restart=True)


@app.post("/automation/reset", response_model=SupervisorStatus)
async def automation_reset():
    try:
        return supervisor().reset()
    except RecoveryBlocked as exc:
        raise HTTPException(409, exc.message) from None


def main():
    if os.getuid() == 0:
        raise SystemExit("Run the ARC agent as an unprivileged user")
    bind = os.environ.get("ARC_AGENT_BIND", "")
    if ipaddress.ip_address(bind) not in ipaddress.ip_network("100.64.0.0/10"):
        raise SystemExit("ARC_AGENT_BIND must be this worker’s Tailscale IPv4 address")
    if bind == "100.118.85.127":
        raise SystemExit("Worker agent must not run on the head")
    uvicorn.run(app, host=bind, port=9071, access_log=False)


if __name__ == "__main__":
    main()
