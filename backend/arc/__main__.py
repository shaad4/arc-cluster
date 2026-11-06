"""Start the API with safe loopback defaults."""

import os

import uvicorn

from arc.config import Settings


def main() -> None:
    if os.getuid() == 0:
        raise SystemExit("ARC must run as an unprivileged user")
    settings = Settings()
    uvicorn.run("arc.main:app", host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
