from fastapi import APIRouter, Request
from pydantic import BaseModel

from arc.services.jobs import Job, JobList, LogResponse, Submission

router = APIRouter()


class SubmissionResult(BaseModel):
    submission_id: str


@router.get("/jobs", response_model=JobList)
async def jobs(request: Request):
    return await request.app.state.jobs.list()


@router.get("/jobs/{job_id}", response_model=Job)
async def job(request: Request, job_id: str):
    return await request.app.state.jobs.get(job_id)


@router.get("/jobs/{job_id}/logs", response_model=LogResponse)
async def logs(request: Request, job_id: str):
    return await request.app.state.jobs.logs(job_id)


@router.post("/workloads/submit", response_model=SubmissionResult, status_code=202)
async def submit(request: Request, data: Submission):
    return await request.app.state.jobs.submit(data)
