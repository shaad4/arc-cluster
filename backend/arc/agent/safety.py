"""Runs in the existing Ray interpreter. Read-only, complete State API checks."""

import dataclasses
import json
import os

from ray.job_submission import JobSubmissionClient
from ray.util.state import list_actors, list_nodes, list_tasks
from safety_rules import workloads_busy

url = os.environ["ARC_AGENT_STATE_URL"]
ip = os.environ["ARC_AGENT_BIND"]
try:
    opts = dict(address=url, timeout=3, limit=10000, raise_on_missing_output=True)
    nodes = [dataclasses.asdict(n) for n in list_nodes(**opts)]
    tasks = [
        dataclasses.asdict(t)
        for t in list_tasks(filters=[("name", "!=", "arc.metrics")], **opts)
    ]
    actors = [dataclasses.asdict(a) for a in list_actors(**opts)]
    jobs = JobSubmissionClient(url).list_jobs()
    busy = workloads_busy(tasks, actors, [dataclasses.asdict(j) for j in jobs])
    member = any(n.get("node_ip") == ip and n["state"] == "ALIVE" for n in nodes)
    print(
        json.dumps(
            {
                "verified": True,
                "member": member,
                "busy": busy,
            }
        )
    )
except Exception:
    print(json.dumps({"verified": False, "member": None, "busy": None}))
