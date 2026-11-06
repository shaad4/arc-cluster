"""Start the API with safe loopback defaults."""

import os

import uvicorn

from arc.config import Settings
from arc.logging_config import configure_logging


def main() -> None:
    if os.getuid() == 0:
        raise SystemExit("ARC must run as an unprivileged user")
    settings = Settings()
    configure_logging()
    uvicorn.run(
        "arc.main:app",
        host=settings.host,
        port=settings.port,
        access_log=False,
        log_config=None,
    )


if __name__ == "__main__":
    main()
