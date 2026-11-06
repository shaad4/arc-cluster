"""Bounded allowlisted tails and conservative secret redaction."""

import re
from pathlib import Path

SECRET = re.compile(
    r"(?i)(authorization|password|passwd|secret|token|api[_-]?key|credential)"
)


def redact(text: str) -> str:
    result = []
    private = False
    for line in text.splitlines()[-500:]:
        if "-----BEGIN " in line:
            private = True
        if (
            private
            or SECRET.search(line)
            or re.search(
                r"AKIA[A-Z0-9]{16}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|^[A-Za-z0-9+/=]{64,}$",
                line,
            )
        ):
            result.append("[redacted sensitive line]")
        else:
            result.append(line[:2000])
        if "-----END " in line:
            private = False
    return "\n".join(result)[-65536:]


def local_tail(source: str) -> str:
    names = {"raylet": "raylet.out", "raylet-error": "raylet.err"}
    if source not in names:
        raise ValueError("Unsupported log source")
    path = Path("/tmp/ray/session_latest/logs") / names[source]
    with path.open("rb") as stream:
        stream.seek(0, 2)
        stream.seek(max(0, stream.tell() - 65536))
        data = stream.read(65536)
    return redact(data.decode("utf-8", errors="replace"))
