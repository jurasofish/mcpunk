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

    # Default indentation when serialising to JSON in response.
    default_response_indent: int | Literal["no_indent"] = 2
    # Whether to include the number of characters in the response in the response.
    # So like `[DEBUG INFO: Response is 1234 chars]` prefixed to the response.
    include_chars_in_response: bool = True
    # Maximum number of characters in the response. If the response is longer than this
    # then an error will be returned to the caller. This is handy to avoid blowing
    # your context.
    default_response_max_chars: int = 20_000
    # Same as `default_response_max_chars` but for the tool that returns a git diff.
    # Generally, git diffs are a bit larger than e.g. a function so nice to have it a
    # bit larger.
    default_git_diff_response_max_chars: int = 50_000

    # A task which is in the "doing" state for longer than this duration
    # will become available again for pickup.
    task_queue_visibility_timeout_seconds: int = 300

    # How long to wait between refreshing files modified on disk. This allows files
    # to queue up and be refreshed in parallel if many are modified (e.g. switching
    # branches), and it generally also avoids churn when e.g. an IDE creates temporary
    # files during save (though this is not a guarantee).
    file_watch_refresh_freq_seconds: float = 0.1

    # Maximum size of a chunk in characters. If a chunk is larger than this,
    # it will be split into multiple chunks. A chunk is something like a function,
    # or maybe a whole file (depends on the chunker).
    max_chunk_size: int = 10_000

    @property
    def task_queue_visibility_timeout(self) -> timedelta:
        return timedelta(seconds=self.task_queue_visibility_timeout_seconds)

    model_config = SettingsConfigDict(
        env_prefix="MCPUNK_",
        validate_default=True,
        frozen=True,
    )
