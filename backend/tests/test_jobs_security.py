import asyncio

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from arc.config import Settings
from arc.main import create_app
from arc.services.jobs import JobService, Submission
from arc.services.logs import redact


def test_submission_validation_and_redaction():
    with pytest.raises(ValidationError):
        Submission(workload="shell", count=1, confirmed=True)
    with pytest.raises(ValidationError):
        Submission(workload="distributed-square", count=101, confirmed=True)
    assert "abc" not in redact("API_TOKEN=abc\nnormal line")
    assert "normal line" in redact("API_TOKEN=abc\nnormal line")


def test_job_errors_and_mutation_guard():
    async def check():
        settings = Settings(collector_enabled=False)
        service = JobService(settings)
        await service.client.aclose()
        service.client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(500)),
            base_url="http://ray",
        )
        with pytest.raises(HTTPException) as error:
            await service.list()
        assert error.value.status_code == 502
        await service.close()
        app = create_app(settings)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://localhost"
            ) as client:
                body = dict(workload="distributed-square", count=4, confirmed=True)
                assert (
                    await client.post("/api/workloads/submit", json=body)
                ).status_code == 403
                headers = {"origin": "http://localhost", "x-arc-request": "1"}
                response = await client.post(
                    "/api/workloads/submit", json=body, headers=headers
                )
                assert response.status_code == 403
                assert "not approved" in response.json()["detail"]
                headers["origin"] = "https://attacker.invalid"
                assert (
                    await client.post(
                        "/api/workloads/submit", json=body, headers=headers
                    )
                ).status_code == 403

    asyncio.run(check())
