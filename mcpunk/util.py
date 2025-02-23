import logging
import random
from collections import defaultdict
from collections.abc import Callable
from copy import deepcopy
from functools import wraps
from pathlib import Path
from string import ascii_lowercase
from typing import ParamSpec, TypeVar, assert_never

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


def log_inputs_outputs(
    log_level: int | str = logging.INFO,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to wrap a tool function and log its inputs and outputs.

    mcp = FastMCP()
    @mcp.tool()
    @log_inputs()
    def get_a_joke(): ...

    Args:
        log_level: The log level to use for the log messages, like `logging.INFO`
            or "INFO", matching those in the `logging` module.
    """
    if isinstance(log_level, str):
        level = logging.getLevelNamesMapping()[log_level]
    else:
        level = log_level

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            lines = [
                "",
                " " * 2 + "./" + "-" * 116 + "\\.",
                " " * 1 + "./" + " " * 118 + "\\.",
                " " * 0 + "./" + " " * 120 + "\\.",
                f"Calling tool {func.__name__} with inputs:",
            ]
            for i, v in enumerate(args):
                lines.append(f"    Arg_{i}={v!r}")
            for k, v in kwargs.items():
                lines.append(f"    {k}={v!r}")
            logger.log(level, "\n".join(lines))
            resp = func(*args, **kwargs)
            lines = [
                "",
                f"    resp={resp!r}",
                " " * 0 + ".\\" + " " * 120 + "/.",
                " " * 1 + ".\\" + " " * 118 + "/.",
                " " * 2 + ".\\" + "-" * 116 + "/.",
            ]
            logger.log(level, "\n".join(lines))
            return resp

        return wrapper

    return decorator


def create_file_tree(
    *,
    project_root: Path,
    paths: set[Path],
    limit_depth_from_root: int | None = None,
    filter_: None | list[str] = None,
) -> str | None:
    """Create a compact text representation of files in a directory structure.

    Outputs files grouped by their parent directory, with each directory and its
    files on a single line. Only includes files, not directories.
    e.g.
    ```
    dir1: file1.txt
    dir2/dir3: file2.txt; file3.txt
    ...
    ```

    Args:
        project_root: The root directory of the project.
        paths: Set of paths to potentially include in the output.
        limit_depth_from_root: If provided, exclude files deeper than this many
            levels from the root directory.
        filter_: If provided, only include paths containing any of these strings.
            None matches all paths.

    Returns:
        None if no files match the criteria, otherwise a string where each line is:
        "{relative_directory_path}: file1.txt; file2.txt; file3.txt"
    """
    paths = deepcopy(paths)  # Avoid mutation shenanigans
    project_root = project_root.absolute()

    filtered_paths = {
        x
        for x in paths
        if matches_filter(filter_, str(x))
        and x.is_file()
        and (
            limit_depth_from_root is None
            or _get_depth_from_root(project_root, x) <= limit_depth_from_root
        )
    }

    if len(filtered_paths) == 0:
        return None

    response = ""
    files_by_parent_dir: dict[Path, list[Path]] = defaultdict(list)
    for p in sorted(filtered_paths):
        files_by_parent_dir[p.parent].append(p)
    for parent_dir in sorted(files_by_parent_dir.keys()):
        response += f"{parent_dir.relative_to(project_root)}: "
        response += "; ".join(x.name for x in files_by_parent_dir[parent_dir])
        response += "\n"
    return response


def _get_depth_from_root(root: Path, file: Path) -> int:
    return len(file.relative_to(root).parts)


def rand_str(n: int = 10, chars: str = ascii_lowercase) -> str:
    return "".join(random.choice(chars) for _ in range(n))


def matches_filter(filter_: None | list[str], data: str | None) -> bool:
    """Return True if the data matches the given filter.

    filter_ can be:
    - None matches all data
    - str matches if the data contains the string
    - list[str] matches if the data contains any of the strings in the list

    if data is None it never matches (unless filter_ is None)
    """
    if filter_ is None:
        return True
    if data is None:
        return False
    if isinstance(filter_, list):
        return any(x in data for x in filter_)
    assert_never(filter_)
