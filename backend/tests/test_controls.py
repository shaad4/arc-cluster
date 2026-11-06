import asyncio

import httpx
import pytest

from arc.config import Settings
from arc.main import create_app
from arc.services.agents import read_credentials


def test_credentials_permissions(tmp_path):
    file = tmp_path / "credentials"
    file.write_text('{"box2": "abcdefghijklmnopqrstuvwxyz0123456789"}')
    file.chmod(0o644)
    with pytest.raises(ValueError):
        read_credentials(str(file))
    file.chmod(0o600)
    assert "box2" in read_credentials(str(file))


def test_unsafe_controls_fail_closed():
    async def check():
        app = create_app(Settings(collector_enabled=False))
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app),
                base_url="http://localhost",
                headers={"origin": "http://localhost", "x-arc-request": "1"},
            ) as client:
                assert (
                    await client.post(
                        "/api/nodes/box1/ray/stop", json={"confirmed": True}
                    )
                ).status_code == 403
                assert (
                    await client.post(
                        "/api/nodes/box2/recover", json={"confirmed": False}
                    )
                ).status_code == 409
                assert (
                    await client.post(
                        "/api/nodes/box2/recover", json={"confirmed": True}
                    )
                ).status_code == 409
                assert (
                    await client.post(
                        "/api/nodes/box2/ray/shell", json={"confirmed": True}
                    )
                ).status_code == 422
                assert (await client.get("/api/nodes/box2/preflight")).json()[
                    "allowed"
                ] is False
                assert (await client.get("/api/logs?node_id=box2")).status_code == 503

    asyncio.run(check())
