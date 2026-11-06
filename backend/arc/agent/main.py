"""Optional non-root Tailscale-only worker agent, separate from dashboard auth."""

import asyncio
import hmac
import ipaddress
import json
import os
from pathlib import Path
from typing import Literal

import psutil
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from arc.collectors.local import collect_local
from arc.services.agents import read_credentials
from arc.services.logs import local_tail

app = FastAPI(title="ARC worker agent", docs_url=None, redoc_url=None, openapi_url=None)
lock = asyncio.Lock()


def ray_process() -> bool:
    return any(p.info["name"] == "raylet" for p in psutil.process_iter(["name"]))


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


async def execute(*args, timeout=15):
    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
    )
    try:
        async with asyncio.timeout(timeout):
            output = await process.stdout.read(65537)
            if len(output) > 65536:
                raise ValueError("Command output exceeded limit")
            await process.wait()
            if process.returncode:
                raise ValueError("Command failed")
            return output
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


async def preflight():
    if os.environ.get("ARC_AGENT_BIND") == "100.118.85.127":
        raise HTTPException(403, "Head controls disabled")
    if os.environ.get("ARC_AGENT_ENABLE_CONTROLS") != "1":
        raise HTTPException(403, "Agent controls disabled in configuration")
    if not os.environ.get("ARC_AGENT_STATE_URL"):
        raise HTTPException(409, "Independent State API access is not configured")
    try:
        result = json.loads(
            await execute(
                "/data/cluster/venv/bin/python",
                str(Path(__file__).with_name("safety.py")),
            )
        )
    except (OSError, ValueError, TimeoutError):
        raise HTTPException(409, "Safety checks unavailable") from None
    if not result.get("verified") or result.get("busy"):
        raise HTTPException(409, "Workloads active or safety state incomplete")
    result["ray_process"] = await asyncio.to_thread(ray_process)
    return result


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
        ray_bin = "/data/cluster/venv/bin/ray"
        try:
            if body.action == "stop" or (
                body.action == "recover" and state["ray_process"]
            ):
                await execute(ray_bin, "stop", "--grace-period=5", timeout=20)
            if body.action in {"start", "recover"}:
                await execute(
                    ray_bin,
                    "start",
                    "--address=100.118.85.127:6379",
                    f"--node-ip-address={os.environ['ARC_AGENT_BIND']}",
                    timeout=25,
                )
        except (OSError, ValueError, TimeoutError):
            raise HTTPException(
                502, "Allowlisted Ray command failed; inspect worker logs"
            ) from None
        return {"executed": True, "action": body.action}


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
