import asyncio

import httpx

from arc.config import Settings
from arc.main import create_app


def test_frontend_routing_and_host_validation(tmp_path):
    (tmp_path / "index.html").write_text("<html>ARC</html>")

    async def check():
        app = create_app(Settings(collector_enabled=False, frontend_dist=str(tmp_path)))
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://localhost"
            ) as client:
                assert (await client.get("/nodes/box2")).text == "<html>ARC</html>"
                assert (await client.get("/api/nope")).status_code == 404
                assert (await client.get("/secret.env")).status_code == 404
                assert (
                    await client.get(
                        "/api/health", headers={"host": "attacker.invalid"}
                    )
                ).status_code == 400

    asyncio.run(check())


def test_default_frontend_path():
    from pathlib import Path

    assert (
        Path(Settings().frontend_dist)
        == Path(__file__).resolve().parents[2] / "frontend" / "dist"
    )
