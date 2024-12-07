from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # SQLite database path
    db_path: Path = Path(
        "~/.mcpunk/db.sqlite",
    ).expanduser()

    # Enable SQLAlchemy query logging
    db_echo: bool = True

    enable_log_file: bool = True
    log_file: Path = Path("~/.mcpunk/mcpunk.log").expanduser()
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "FATAL", "CRITICAL"] = "DEBUG"

    model_config = SettingsConfigDict(
        env_prefix="MCPUNK_",
    )
