"""Isolated JSON-lines bridge. Executed ONLY with the existing Ray interpreter."""

import contextlib
import dataclasses
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

# stdout is reserved for protocol messages, including during Ray initialization.
protocol = sys.stdout
sys.stdout = sys.stderr
import ray  # noqa: E402
from ray.job_submission import JobSubmissionClient  # noqa: E402
from ray.util.scheduling_strategies import NodeAffinitySchedulingStrategy  # noqa: E402
from ray.util.state import list_actors, list_tasks  # noqa: E402


def measure():
    import socket
    import time

    import psutil

    cpu = psutil.cpu_percent(interval=0.15)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/data")
    network = psutil.net_io_counters()
    return dict(
        timestamp=time.time(),
        hostname=socket.gethostname(),
        cpu_percent=cpu,
        cpu_count=psutil.cpu_count(),
        memory_total=memory.total,
        memory_used=memory.total - memory.available,
        memory_percent=memory.percent,
        disk_total=disk.total,
        disk_used=disk.used,
        disk_percent=disk.percent,
        net_sent=network.bytes_sent,
        net_recv=network.bytes_recv,
        uptime=time.time() - psutil.boot_time(),
    )


remote_measure = ray.remote(num_cpus=0, max_retries=0)(measure)
address = os.environ.get("ARC_RAY_ADDRESS", "100.118.85.127:6379")
dashboard = os.environ.get("ARC_RAY_DASHBOARD", "http://127.0.0.1:8265")


def encode(value):
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if hasattr(value, "asdict"):
        return value.asdict()
    if hasattr(value, "dict"):
        return value.dict()
    return str(value)


def state(fn):
    try:
        filters = [("name", "!=", "arc.metrics")] if fn is list_tasks else None
        result = fn(
            filters=filters,
            address=dashboard,
            timeout=3,
            limit=1000,
            raise_on_missing_output=True,
        )
        return {"items": [encode(x) for x in result], "error": None}
    except Exception:
        return {"items": [], "error": "State API unavailable or incomplete"}


def snapshot():
    if not ray.is_initialized():
        ray.init(
            address=address,
            namespace="arc-monitor",
            job_config=ray.job_config.JobConfig(metadata={"arc.component": "monitor"}),
            logging_level="ERROR",
            log_to_driver=False,
        )
    nodes = ray.nodes()
    metrics = {}
    refs = {}
    for node in nodes:
        if node["Alive"]:
            ref = remote_measure.options(
                name="arc.metrics",
                scheduling_strategy=NodeAffinitySchedulingStrategy(
                    node_id=node["NodeID"], soft=False
                ),
            ).remote()
            refs[ref] = node["NodeID"]
    ready, pending = (
        ray.wait(list(refs), num_returns=len(refs), timeout=3) if refs else ([], [])
    )
    for ref in ready:
        with contextlib.suppress(Exception):
            metrics[refs[ref]] = ray.get(ref)
    for ref in pending:
        ray.cancel(ref, force=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        tasks = pool.submit(state, list_tasks)
        actors = pool.submit(state, list_actors)
        tasks, actors = tasks.result(), actors.result()
    return dict(
        version=ray.__version__,
        nodes=[
            {
                "id": n["NodeID"],
                "ip": n["NodeManagerAddress"],
                "alive": n["Alive"],
                "resources": n.get("Resources", {}),
            }
            for n in nodes
        ],
        total=ray.cluster_resources(),
        available=ray.available_resources(),
        metrics=metrics,
        tasks=tasks,
        actors=actors,
    )


try:
    for line in sys.stdin:
        try:
            request = json.loads(line)
            if request["op"] == "snapshot":
                result = snapshot()
            elif request["op"] == "jobs":
                result = [
                    dataclasses.asdict(j)
                    for j in JobSubmissionClient(dashboard).list_jobs()
                ][:1000]
            else:
                raise ValueError("Unsupported operation")
            reply = {"ok": True, "data": result}
        except Exception:
            if ray.is_initialized():
                ray.shutdown()
            reply = {"ok": False, "error": "Ray bridge operation failed"}
        protocol.write(json.dumps(reply, default=encode) + "\n")
        protocol.flush()
finally:
    ray.shutdown()
