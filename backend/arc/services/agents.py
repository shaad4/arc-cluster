import asyncio
import json
import os
import stat
from pathlib import Path

import httpx
from fastapi import HTTPException


def read_credentials(path: str) -> dict[str, str]:
    if not path:
        return {}
    file = Path(path)
    info = file.stat()
    if stat.S_IMODE(info.st_mode) & 0o077 or info.st_uid != os.getuid():
        raise ValueError("Agent credentials must be owned by ARC and mode 0600")
    data = json.loads(file.read_text())
    if not isinstance(data, dict) or any(
        not isinstance(v, str) or len(v) < 32 for v in data.values()
    ):
        raise ValueError("Agent credentials must map node names to strong tokens")
    return data


class AgentClient:
    def __init__(self, settings):
        self.settings = settings
        self.credentials = read_credentials(settings.agent_credentials_file)
        self.client = httpx.AsyncClient(
            timeout=3, trust_env=False, limits=httpx.Limits(max_connections=5)
        )

    async def close(self):
        await self.client.aclose()

    async def request(self, node, method, path, timeout=3, **kwargs):
        token = self.credentials.get(node.id)
        if not token:
            raise HTTPException(503, "Worker agent credentials are not configured")
        try:
            async with self.client.stream(
                method,
                f"http://{node.ip}:{self.settings.agent_port}{path}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=timeout,
                **kwargs,
            ) as response:
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > 128 * 1024:
                        raise HTTPException(502, "Agent response too large")
                data = json.loads(content)
                if response.is_error:
                    raise HTTPException(
                        response.status_code,
                        "Agent rejected request or safety preflight failed",
                    )
                return data
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(503, "Worker agent unavailable") from exc

    async def collect(self, nodes):
        async def one(node):
            if node.id not in self.credentials:
                return node.id, {"status": "not configured"}
            try:
                data = await self.request(node, "GET", "/health")
                return node.id, {"status": "online", **data}
            except HTTPException:
                return node.id, {"status": "unavailable"}

        return dict(await asyncio.gather(*(one(n) for n in nodes)))
