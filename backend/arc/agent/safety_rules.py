"""Pure safety rules shared with the isolated Ray interpreter (stdlib only)."""


def workloads_busy(tasks, actors, jobs):
    if len(jobs) > 10000:
        raise ValueError("Job inventory exceeds safety limit")
    if any(t.get("state") not in {"FINISHED", "FAILED"} for t in tasks):
        return True
    if any(a.get("state") != "DEAD" for a in actors):
        return True
    for job in jobs:
        # Only ARC's explicitly marked read-only bridge driver is exempt.
        # User driver jobs matter just as much as Jobs API submissions.
        monitor = (
            job.get("type") == "DRIVER"
            and (job.get("metadata") or {}).get("arc.component") == "monitor"
            and "/arc/bridge/worker.py" in (job.get("entrypoint") or "")
        )
        if not monitor and job.get("status") not in {"SUCCEEDED", "FAILED", "STOPPED"}:
            return True
    return False
