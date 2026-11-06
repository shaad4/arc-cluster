import json
import logging
import time


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
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("arc")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
