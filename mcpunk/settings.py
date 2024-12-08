from datetime import timedelta
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # SQLite database path
    db_path: Path = Path("~/.mcpunk/db.sqlite").expanduser()

    # Enable SQLAlchemy query logging
    db_echo: bool = True

    enable_log_file: bool = True
    log_file: Path = Path("~/.mcpunk/mcpunk.log").expanduser()
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "FATAL", "CRITICAL"] = "DEBUG"

    default_response_indent: int | Literal["no_indent"] = 2
    include_chars_in_response: bool = True

    # A task which is in the "doing" state for longer than this duration
    # will become available again for pickup.
    task_queue_visibility_timeout_seconds: int = 300

    @property
    def task_queue_visibility_timeout(self) -> timedelta:
        return timedelta(seconds=self.task_queue_visibility_timeout_seconds)

    model_config = SettingsConfigDict(
        env_prefix="MCPUNK_",
    )
