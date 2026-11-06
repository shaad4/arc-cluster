"""Environment-based service configuration (ARC_ prefix)."""

from importlib.metadata import version

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARC_")

    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)


APP_NAME = "ARC"
APP_VERSION = version("arc-backend")
