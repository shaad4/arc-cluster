"""Allowlisted local Ray operations. All network/process evidence is rechecked."""

import asyncio
import fcntl
import json
import os
from contextlib import contextmanager
from pathlib import Path

import psutil

from arc.agent.supervisor import RecoveryBlocked
from arc.models.recovery import WorkerObservation

HEAD = "100.118.85.127"
WORKER_IPS = {
    "box2": "100.124.19.50",
    "box3": "100.64.151.60",
    "box4": "100.93.80.83",
    "box5": "100.96.223.107",
}
RAY = "/data/cluster/venv/bin/ray"


async def execute(*args, timeout=15):
    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
    )
    try:
        async with asyncio.timeout(timeout):
            # read(n) can return a partial read: drain until EOF, enforcing total cap.
            chunks = bytearray()
            while chunk := await process.stdout.read(8192):
                chunks.extend(chunk)
                if len(chunks) > 65536:
                    raise ValueError("Command output exceeded limit")
            await process.wait()
            if process.returncode:
                raise ValueError("Command failed")
            return bytes(chunks)
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


def ray_process():
    return any(p.info["name"] == "raylet" for p in psutil.process_iter(["name"]))


class WorkerOperations:
    def __init__(self, directory: Path):
        self.directory = directory

    @contextmanager
    def guard(self):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (self.directory / "operation.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RecoveryBlocked(
                    "recovering", "Another local Ray operation is active"
                ) from None
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    async def identity(self):
        try:
            raw = await execute("/usr/bin/tailscale", "status", "--json", timeout=4)
            status = json.loads(raw)
            if status.get("BackendState") != "Running":
                raise ValueError("Tailscale not running")
            addresses = status.get("TailscaleIPs", [])
            ip = next((ip for ip in addresses if ip in WORKER_IPS.values()), None)
            if not ip or ip != os.environ.get("ARC_AGENT_BIND"):
                raise ValueError("Worker IP does not match configured identity")
            return ip
        except (OSError, ValueError, StopIteration):
            raise RecoveryBlocked(
                "waiting_for_node", "Tailscale unavailable or worker identity mismatch"
            ) from None
        except TimeoutError:
            raise RecoveryBlocked("waiting_for_node", "Tailscale timed out") from None

    async def head_reachable(self, ip):
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(HEAD, 6379, local_addr=(ip, 0)), 3
            )
            writer.close()
            await writer.wait_closed()
        except (OSError, TimeoutError):
            raise RecoveryBlocked(
                "waiting_for_node", "Head unreachable over Tailscale"
            ) from None

    async def state(self):
        if not os.environ.get("ARC_AGENT_STATE_URL"):
            raise RecoveryBlocked(
                "manual_intervention_required",
                "Independent State API access is not configured",
            )
        try:
            data = json.loads(
                await execute(
                    "/data/cluster/venv/bin/python",
                    str(Path(__file__).with_name("safety.py")),
                    timeout=15,
                )
            )
            if (
                data.get("verified") is not True
                or type(data.get("member")) is not bool
                or type(data.get("busy")) is not bool
            ):
                raise ValueError("Incomplete workload state")
            return data
        except (OSError, ValueError, TimeoutError):
            raise RecoveryBlocked(
                "manual_intervention_required",
                "Complete workload or membership state unavailable",
            ) from None

    async def observe(self):
        ip = await self.identity()
        await self.head_reachable(ip)
        data = await self.state()
        try:
            process = await asyncio.to_thread(ray_process)
        except (psutil.Error, OSError):
            raise RecoveryBlocked(
                "manual_intervention_required", "Local Ray process state unknown"
            ) from None
        return WorkerObservation(tailscale_ip=ip, ray_process=process, **data)

    async def change(self, action, ip, authorized=lambda: True):
        if os.environ.get("ARC_AGENT_ENABLE_CONTROLS") != "1":
            raise RecoveryBlocked(
                "manual_intervention_required", "Agent controls are not approved"
            )
        current = await self.observe()
        if not authorized():
            raise RecoveryBlocked(
                "disabled", "Controller permission expired or disabled"
            )
        if current.tailscale_ip != ip or current.busy or not current.verified:
            raise RecoveryBlocked(
                "manual_intervention_required", "Safety state changed before execution"
            )
        if action not in {"start", "stop", "recover"}:
            raise ValueError("Unsupported action")
        if action != "stop" and current.member:
            raise RecoveryBlocked("healthy", "Worker is already a live member")
        if action == "start" and current.ray_process:
            raise RecoveryBlocked("worker_disconnected", "Ray process already exists")
        if action == "stop" or (action == "recover" and current.ray_process):
            await execute(RAY, "stop", "--grace-period=5", timeout=20)
        if action != "stop":
            # Stop may return before all processes exit; never duplicate a raylet.
            if await asyncio.to_thread(ray_process):
                raise RecoveryBlocked(
                    "manual_intervention_required",
                    "Existing Ray process has not exited",
                )
            if not authorized():
                raise RecoveryBlocked(
                    "disabled", "Automatic recovery disabled before start"
                )
            await execute(
                RAY,
                "start",
                f"--address={HEAD}:6379",
                f"--node-ip-address={ip}",
                timeout=25,
            )

    async def verify(self, ip):
        # Bounded full verification, including actual membership, not just a PID.
        for _ in range(3):
            await asyncio.sleep(2)
            state = await self.observe()
            if state.member and state.ray_process and state.tailscale_ip == ip:
                return True
        return False
