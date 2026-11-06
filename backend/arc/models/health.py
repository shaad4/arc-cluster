from typing import Literal

from pydantic import AwareDatetime, BaseModel


class HealthResponse(BaseModel):
    name: Literal["ARC"]
    version: str
    status: Literal["ok"]
    timestamp: AwareDatetime
