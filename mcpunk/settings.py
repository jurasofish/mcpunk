from pathlib import Path
from typing import Annotated

from pydantic import (
    Field,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    db_path: Annotated[Path, Field(description="SQLite database path")] = Path(
        "~/.task_db.sqlite",
    ).expanduser()
    db_echo: Annotated[bool, Field(description="Enable SQLAlchemy query logging")] = True

    model_config = SettingsConfigDict(
        env_prefix="MCPUNK_",
    )


_settings = Settings()


def get_settings() -> Settings:
    return _settings
