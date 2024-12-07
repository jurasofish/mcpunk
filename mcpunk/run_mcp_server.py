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

from mcpunk.db import init_db
from mcpunk.dependencies import Dependencies
from mcpunk.tools import mcp


def _setup_logging() -> logging.Logger:
    settings = Dependencies().settings()
    _logger = logging.getLogger("mcpunk")
    _logger.setLevel(settings.log_level)
    if settings.enable_log_file:
        log_path = settings.log_file.expanduser().absolute()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(settings.log_level)

        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            ),
        )
        _logger.addHandler(file_handler)

    return _logger


logger = _setup_logging()
logger.debug("Logging started")


def main() -> None:
    logger.info("Initializing database")
    init_db()
    logger.info("Starting mcp server")
    mcp.run()


if __name__ == "__main__":
    main()
