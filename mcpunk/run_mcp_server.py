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
import pathlib

from mcpunk.tools import mcp


def _setup_logging() -> logging.Logger:
    log_dir = pathlib.Path.home() / ".commit_summariser"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "mcp_server.log"
    _logger = logging.getLogger("commit_summariser")
    _logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    _logger.addHandler(file_handler)

    return _logger


logger = _setup_logging()
logger.debug("Logging started")


def main() -> None:
    logger.debug("Running mcp server")
    mcp.run()


if __name__ == "__main__":
    main()
