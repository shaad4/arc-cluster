"""Runs in the existing Ray interpreter. Read-only, complete State API checks."""

import dataclasses
import json
import os

from ray.job_submission import JobSubmissionClient
from ray.util.state import list_actors, list_nodes, list_tasks

url = os.environ["ARC_AGENT_STATE_URL"]
ip = os.environ["ARC_AGENT_BIND"]
try:
    opts = dict(address=url, timeout=3, limit=10000, raise_on_missing_output=True)
    nodes = [dataclasses.asdict(n) for n in list_nodes(**opts)]
    tasks = [dataclasses.asdict(t) for t in list_tasks(**opts)]
    actors = [dataclasses.asdict(a) for a in list_actors(**opts)]
    jobs = JobSubmissionClient(url).list_jobs()
    # Conservatively refuse mutations while ANY user job/task/actor is active.
    active_tasks = [
        t
        for t in tasks
        if t["state"] not in {"FINISHED", "FAILED"} and t.get("name") != "arc.metrics"
    ]
    active_actors = [a for a in actors if a["state"] != "DEAD"]
    active_jobs = [
        j
        for j in jobs
        if str(j.status) in {"PENDING", "RUNNING"}
        and getattr(j, "type", "") == "SUBMISSION"
    ]
    member = any(n.get("node_ip") == ip and n["state"] == "ALIVE" for n in nodes)
    print(
        json.dumps(
            {
                "verified": True,
                "member": member,
                "busy": bool(active_tasks or active_actors or active_jobs),
            }
        )
    )
except Exception:
    print(json.dumps({"verified": False, "member": None, "busy": None}))
