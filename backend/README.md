# ARC backend

The maintained installation, API, testing, security, and deployment instructions
are in the [project README](../README.md). Implementation boundaries are described
in [architecture](../docs/architecture.md).

From the repository root:

```sh
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -e './backend[dev]'
backend/.venv/bin/python -m arc
```

Default: `127.0.0.1:8000`. `/api/health` reports application liveness only. Build
`frontend/dist` to serve the dashboard. Do not install ARC dependencies into
`/data/cluster/venv`, which is used only by the isolated Ray bridge.
