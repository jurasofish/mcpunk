"""Entry point for running MCPunk.

--------------------------------------------------------------------------------
PRODUCTION
--------------------------------------------------------------------------------

Just
```
{
  "mcpServers": {
    "MCPunk": {
      "command": "/Users/michael/.local/bin/uvx",
      "args": [
        "mcpunk"
      ]
    }
  }
}
```

--------------------------------------------------------------------------------
DEVELOPMENT
--------------------------------------------------------------------------------

Can run on command line with `uvx --from /Users/michael/git/mcpunk --no-cache mcpunk`

Can add to claude like
```
{
  "mcpServers": {
    "MCPunk": {
      "command": "/Users/michael/.local/bin/uvx",
      "args": [
        "--from",
        "/Users/michael/git/mcpunk",
        "--no-cache",
        "mcpunk"
      ]
    }
  }
}
```
"""

# This file is a target for `fastmcp run .../run_mcp_server.py`
import logging
import sys

from mcpunk.db import init_db
from mcpunk.dependencies import Dependencies
from mcpunk.tools import mcp


def _setup_logging() -> logging.Logger:
    """Aggressively control global logging.

    It seems that some MCP clients are messed up by looking at stderr,
    here we remove all log handlers and configure them ourselves with
    careful control.
    """
    settings = Dependencies().settings()

    root_logger = logging.getLogger()

    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        handler.close()

    root_logger.setLevel(settings.log_level)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if settings.enable_stderr_logging:
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setLevel(settings.log_level)
        stderr_handler.setFormatter(formatter)
        root_logger.addHandler(stderr_handler)

    if settings.enable_log_file:
        log_path = settings.log_file.expanduser().absolute()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(settings.log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Get module logger (will inherit from root)
    return logging.getLogger(__name__)


logger = _setup_logging()
logger.debug("Logging started")


def main() -> None:
    logger.info("Initializing database")
    init_db()
    logger.info("Starting mcp server")
    mcp.run()


if __name__ == "__main__":
    main()
