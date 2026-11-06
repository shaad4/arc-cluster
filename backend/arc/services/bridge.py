"""One bounded request at a time; restart only our own bridge on timeout."""

import asyncio
import json
import os
from pathlib import Path

from arc.config import Settings


class BridgeUnavailable(Exception):
    pass


class RayBridge:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.process = None
        self.lock = asyncio.Lock()

    async def call(self, operation: str):
        try:
            async with asyncio.timeout(self.settings.bridge_timeout):
                async with self.lock:
                    if self.process is None or self.process.returncode is not None:
                        self.process = await asyncio.create_subprocess_exec(
                            self.settings.ray_python,
                            "-u",
                            str(Path(__file__).parents[1] / "bridge" / "worker.py"),
                            stdin=asyncio.subprocess.PIPE,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.DEVNULL,
                            limit=4 * 1024 * 1024,
                            env={
                                **os.environ,
                                "ARC_RAY_ADDRESS": self.settings.ray_address,
                                "ARC_RAY_DASHBOARD": self.settings.ray_dashboard,
                            },
                        )
                    self.process.stdin.write(
                        json.dumps({"op": operation}).encode() + b"\n"
                    )
                    await self.process.stdin.drain()
                    line = await self.process.stdout.readline()
                    reply = json.loads(line)
                    if not reply["ok"]:
                        raise BridgeUnavailable(reply["error"])
                    return reply["data"]
        except (TimeoutError, OSError, ValueError, KeyError, BridgeUnavailable) as exc:
            await self.close()
            raise BridgeUnavailable("Ray is unavailable or timed out") from exc

    async def close(self):
        process, self.process = self.process, None
        if process and process.returncode is None:
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), 3)
            except TimeoutError:
                process.kill()
                await process.wait()
            except ProcessLookupError:
                pass
