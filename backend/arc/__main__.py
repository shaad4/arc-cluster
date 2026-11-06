"""Start the API with safe loopback defaults."""

import uvicorn

from arc.config import Settings


def main() -> None:
    settings = Settings()
    uvicorn.run("arc.main:app", host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
