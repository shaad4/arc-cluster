"""Environment-based service configuration (ARC_ prefix)."""

from importlib.metadata import version

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARC_")

    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    ray_python: str = "/data/cluster/venv/bin/python"
    ray_address: str = "100.118.85.127:6379"
    ray_dashboard: str = "http://127.0.0.1:8265"
    bridge_timeout: float = Field(default=15, ge=2, le=60)
    poll_interval: int = Field(default=5, ge=5, le=60)
    stale_after: int = Field(default=20, ge=10, le=120)
    collector_enabled: bool = True
    local_node: str = "box1"
    agent_port: int = 9071
    agent_credentials_file: str = ""
    approved_workload: bool = False
    frontend_dist: str = str(
        __import__("pathlib").Path(__file__).resolve().parents[3] / "frontend" / "dist"
    )


APP_NAME = "ARC"
APP_VERSION = version("arc-backend")
