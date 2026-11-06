import pytest

from arc.agent.safety_rules import workloads_busy


@pytest.mark.parametrize(
    "job",
    [
        {"type": "DRIVER", "status": "RUNNING"},
        {"type": "SUBMISSION", "status": "RUNNING"},
        {"type": "SUBMISSION", "status": "PENDING"},
        {"type": "DRIVER", "status": "UNKNOWN"},
        {"type": "DRIVER"},
    ],
)
def test_active_or_unknown_jobs_block(job):
    assert workloads_busy([], [], [job])


def test_only_marked_monitor_driver_is_exempt():
    monitor = {
        "type": "DRIVER",
        "status": "RUNNING",
        "metadata": {"arc.component": "monitor"},
        "entrypoint": "python /application/arc/bridge/worker.py",
    }
    assert not workloads_busy([], [], [monitor])
    assert workloads_busy([{"state": "RUNNING"}], [], [monitor])
    assert workloads_busy([], [{"state": "ALIVE"}], [monitor])
    assert workloads_busy([], [], [{**monitor, "entrypoint": "python user_job.py"}])
    assert not workloads_busy(
        [{"state": "FINISHED"}], [{"state": "DEAD"}], [{"status": "SUCCEEDED"}]
    )
