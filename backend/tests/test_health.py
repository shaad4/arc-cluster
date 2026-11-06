import asyncio
from datetime import UTC, datetime
from importlib.metadata import version

from httpx import ASGITransport, AsyncClient

from arc.config import Settings
from arc.main import create_app


def test_health_contract_and_server_timestamp():
    async def check():
        app = create_app(Settings(collector_enabled=False))
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                before = datetime.now(UTC)
                response = await client.get("/api/health")
                after = datetime.now(UTC)
                assert response.status_code == 200
                assert response.headers["content-type"] == "application/json"
                assert response.headers["cache-control"] == "no-store"
                body = response.json()
                assert set(body) == {"name", "version", "status", "timestamp"}
                assert body["name"] == "ARC"
                assert body["version"] == version("arc-backend")
                assert body["status"] == "ok"
                timestamp = datetime.fromisoformat(body["timestamp"])
                assert timestamp.utcoffset().total_seconds() == 0
                assert before <= timestamp <= after

                next_before = datetime.now(UTC)
                next_response = await client.get("/api/health")
                next_timestamp = datetime.fromisoformat(
                    next_response.json()["timestamp"]
                )
                assert next_before <= next_timestamp <= datetime.now(UTC)

    asyncio.run(check())


def test_health_is_documented_as_application_liveness():
    schema = create_app(Settings(collector_enabled=False)).openapi()
    operation = schema["paths"]["/api/health"]["get"]
    assert "does not check Ray" in operation["description"]
    response = operation["responses"]["200"]["content"]["application/json"]
    assert response["schema"]["$ref"].endswith("/HealthResponse")
