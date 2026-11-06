"""Shared automatic-recovery contracts; all automation defaults off."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

WorkerID = Literal["box2", "box3", "box4", "box5"]


class RecoveryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    enabled: bool = False
    interval: int = Field(default=30, ge=10, le=300)
    max_retries: int = Field(default=3, ge=1, le=8)


class AgentPolicy(RecoveryPolicy):
    lease_seconds: int = Field(default=90, ge=30, le=660)


class RecoveryConfiguration(RecoveryPolicy):
    nodes: dict[WorkerID, bool] = Field(
        default_factory=lambda: {
            "box2": False,
            "box3": False,
            "box4": False,
            "box5": False,
        }
    )


class RecoveryUpdate(RecoveryConfiguration):
    confirmed: bool = False


class RecoveryEvent(BaseModel):
    sequence: int
    timestamp: float
    message: str
    state: str


class SupervisorStatus(BaseModel):
    approved: bool = False
    enabled: bool = False
    lease_expires: float | None = None
    state: str = "disabled"
    message: str = "Automatic recovery is disabled"
    attempts: int = 0
    last_attempt: float | None = None
    last_result: str | None = None
    next_attempt: float | None = None
    manual_hold: bool = False
    events: list[RecoveryEvent] = Field(default_factory=list)


class WorkerObservation(BaseModel):
    model_config = ConfigDict(strict=True)
    tailscale_ip: str
    member: bool
    ray_process: bool
    verified: bool
    busy: bool
