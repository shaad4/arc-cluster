import asyncio
import json
import re
import time
from pathlib import Path

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from arc.services.logs import redact


class Job(BaseModel):
    id: str
    name: str
    status: str
    submission_id: str | None = None
    start_time: int | None = None
    end_time: int | None = None
    entrypoint: str = ""
    message: str | None = None
    type: str = "SUBMISSION"


class JobList(BaseModel):
    items: list[Job]
    error: str | None = None


class LogResponse(BaseModel):
    text: str
    source: str
    truncated: bool = True


class Submission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workload: str = Field(pattern="^distributed-square$")
    count: int = Field(default=8, ge=1, le=100, strict=True)
    confirmed: bool


class JobService:
    def __init__(self, settings):
        self.settings = settings
        self.cache = None
        self.cached_at = 0.0
        self.lock = asyncio.Lock()
        self.client = httpx.AsyncClient(
            base_url=settings.ray_dashboard, timeout=5, trust_env=False
        )

    async def close(self):
        await self.client.aclose()

    async def request(self, method, path, **kwargs):
        try:
            async with self.client.stream(method, path, **kwargs) as response:
                if response.status_code == 404:
                    raise HTTPException(404, "Ray job not found")
                if response.is_error:
                    raise HTTPException(502, "Ray Jobs API rejected the request")
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > 1024 * 1024:
                        raise HTTPException(502, "Ray response exceeds the 1 MiB limit")
                return json.loads(data)
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(503, "Ray Jobs API unavailable") from exc

    async def list(self):
        async with self.lock:
            if self.cache is not None and time.monotonic() - self.cached_at < 5:
                return self.cache
            async with asyncio.timeout(6):
                self.cache = await self.fetch_jobs()
            self.cached_at = time.monotonic()
            return self.cache

    async def fetch_jobs(self):
        data = await self.request("GET", "/api/jobs/")
        return JobList(
            items=[
                Job(
                    id=j.get("submission_id") or j.get("job_id") or "unknown",
                    submission_id=j.get("submission_id"),
                    name=(j.get("metadata") or {}).get("name")
                    or j.get("submission_id")
                    or j.get("job_id")
                    or "Driver",
                    status=j["status"],
                    start_time=j.get("start_time"),
                    end_time=j.get("end_time"),
                    entrypoint=redact(j.get("entrypoint", "")),
                    message=redact(j.get("message") or ""),
                    type=j.get("type", "SUBMISSION"),
                )
                for j in data[:1000]
            ]
        )

    async def get(self, job_id):
        self.validate_id(job_id)
        jobs = await self.list()
        job = next((j for j in jobs.items if j.id == job_id), None)
        if job is None:
            raise HTTPException(404, "Ray job not found")
        return job

    @staticmethod
    def validate_id(value):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
            raise HTTPException(422, "Invalid job identifier")

    async def logs(self, job_id):
        self.validate_id(job_id)
        value = await self.request("GET", f"/api/jobs/{job_id}/logs")
        return LogResponse(text=redact(value.get("logs", "")), source="job")

    async def submit(self, data: Submission):
        if not self.settings.approved_workload:
            raise HTTPException(
                403, "Example workload is not approved in server configuration"
            )
        if not data.confirmed:
            raise HTTPException(409, "Explicit confirmation required")
        # Path and entrypoint are server-owned; only an integer parameter is accepted.
        path = Path(__file__).parents[1] / "workloads" / "distributed_square.py"
        command = f"{self.settings.ray_python} {path} --count {data.count}"
        result = await self.request(
            "POST",
            "/api/jobs/",
            json={
                "entrypoint": command,
                "metadata": {"name": "ARC distributed square"},
                "entrypoint_num_cpus": 0,
            },
        )
        return {"submission_id": result["submission_id"]}
