from datetime import timedelta
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AfterValidator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _post_fiddle_path(p: Path) -> Path:
    return p.expanduser().absolute()


class Settings(BaseSettings):
    # SQLite database path
    db_path: Annotated[
        Path,
        AfterValidator(_post_fiddle_path),
    ] = Path("~/.mcpunk/db.sqlite")

    # I believe that MCP clients should not look at stderr, but it seems some do
    # which completely messes with things. Suggest leaving this off and relying
    # on the log *file* instead.
    enable_stderr_logging: bool = False

    enable_log_file: bool = True
    log_file: Annotated[
        Path,
        AfterValidator(_post_fiddle_path),
    ] = Path("~/.mcpunk/mcpunk.log")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "FATAL", "CRITICAL"] = "INFO"

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
        validate_default=True,
        frozen=True,
    )
