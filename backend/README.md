# ARC backend

Requires Python 3.13 or newer. From the repository root:

```sh
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -e './backend[dev]'
backend/.venv/bin/python -m arc
```

The service binds to `127.0.0.1:8000`. API documentation is at
`http://127.0.0.1:8000/docs`. `ARC_PORT` overrides the port; `ARC_HOST` overrides
the bind address. Keep loopback binding unless a private access design has been
reviewed. There is no application authentication; do not expose this API publicly.
Configuration reads environment variables, not `.env` files.

This environment is independent of `/data/cluster/venv`. Installation and startup
do not import Ray, connect to the cluster, or change its configuration.

Run validation:

```sh
cd backend
.venv/bin/python -m pytest
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

Unexpected errors return a generic JSON error with HTTP 500; tracebacks stay in
server logs. FastAPI retains its standard HTTP and request-validation errors.

`GET /api/health` reports application liveness: `name` (`ARC`), installed package
`version`, `status` (`ok`), and a fresh UTC `timestamp` in ISO 8601 format. Responses
disable caching. This endpoint does not check Ray membership, cluster health,
or machine reachability.

```sh
curl http://127.0.0.1:8000/api/health
```
