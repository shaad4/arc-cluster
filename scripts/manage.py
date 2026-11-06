#!/usr/bin/env python3
"""Unprivileged service alternative; acts only on a verified ARC-owned process."""

import argparse
import fcntl
import json
import os
import signal
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime"
COMMAND = [str(ROOT / "backend/.venv/bin/python"), "-m", "arc"]


def owned_process(record):
    try:
        pid = int(record["pid"])
        args = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")[:-1]
        start_time = Path(f"/proc/{pid}/stat").read_text().split()[21]
        return (
            args == [s.encode() for s in COMMAND] and start_time == record["start_time"]
        )
    except (OSError, ValueError, KeyError):
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "stop", "restart", "status"])
    action = parser.parse_args().action
    if os.getuid() == 0:
        raise SystemExit("Run ARC as an unprivileged user")
    RUNTIME.mkdir(mode=0o700, exist_ok=True)
    with (RUNTIME / "manager.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        record_file = RUNTIME / "process.json"
        try:
            record = json.loads(record_file.read_text())
        except (OSError, ValueError):
            record = {}
        running = owned_process(record)
        if action == "status":
            print(
                f"ARC {'running, PID ' + str(record['pid']) if running else 'stopped'}"
            )
            return
        if action in {"stop", "restart"} and running:
            os.kill(record["pid"], signal.SIGTERM)
            for _ in range(100):
                if not owned_process(record):
                    break
                time.sleep(0.1)
            else:
                raise SystemExit("ARC did not stop gracefully; inspect it manually")
            record_file.unlink(missing_ok=True)
            running = False
        if action in {"start", "restart"}:
            if running:
                print("ARC already running")
                return
            if not (ROOT / "frontend/dist/index.html").is_file():
                raise SystemExit("Build frontend first")
            # Rotate on start; runtime output contains no request bodies or credentials.
            log_path = RUNTIME / "bootstrap.log"
            if log_path.exists() and log_path.stat().st_size > 1024 * 1024:
                log_path.replace(RUNTIME / "bootstrap.previous.log")
            with log_path.open("ab") as log:
                process = subprocess.Popen(
                    COMMAND,
                    cwd=ROOT,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=log,
                    env={**os.environ, "ARC_LOG_FILE": str(RUNTIME / "arc.log")},
                    start_new_session=True,
                )
            time.sleep(0.5)
            if process.poll() is not None:
                raise SystemExit("ARC failed to start; inspect .runtime/arc.log")
            start_time = Path(f"/proc/{process.pid}/stat").read_text().split()[21]
            record_file.write_text(
                json.dumps({"pid": process.pid, "start_time": start_time})
            )
            record_file.chmod(0o600)
            print(f"ARC started, PID {process.pid}; http://127.0.0.1:8000")


if __name__ == "__main__":
    main()
