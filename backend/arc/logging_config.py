import json
import logging
import os
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path


class JsonFormatter(logging.Formatter):
    def format(self, record):
        # Do not serialize exception text or request bodies, which may contain secrets.
        return json.dumps(
            {
                "timestamp": time.time(),
                "level": record.levelname,
                "logger": record.name,
                "event": record.getMessage(),
                "exception_type": record.exc_info[0].__name__
                if record.exc_info
                else None,
            }
        )


def configure_logging():
    log_path = os.environ.get("ARC_LOG_FILE")
    if log_path:
        path = Path(log_path)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        handler = RotatingFileHandler(path, maxBytes=1024 * 1024, backupCount=2)
    else:
        handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    for name in ["arc", "uvicorn"]:
        logger = logging.getLogger(name)
        for old_handler in logger.handlers:
            old_handler.close()
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False
