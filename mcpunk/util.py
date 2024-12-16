import json
import logging
import random
from collections.abc import Callable
from copy import deepcopy
from functools import wraps
from pathlib import Path
from string import ascii_lowercase
from typing import Any, ParamSpec, TypeVar, assert_never

from pydantic_core import to_jsonable_python

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


def log_inputs(func: Callable[P, R]) -> Callable[P, R]:
    """Decorator to wrap a tool function and log its inputs and outputs.

    mcp = FastMCP()
    @mcp.tool()
    @log_inputs
    def get_a_joke(): ...
    """

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
        logger.debug("\n".join(lines))
        resp = func(*args, **kwargs)
        lines = [
            "",
            f"    resp={resp!r}",
            " " * 0 + ".\\" + " " * 120 + "/.",
            " " * 1 + ".\\" + " " * 118 + "/.",
            " " * 2 + ".\\" + "-" * 116 + "/.",
        ]
        logger.debug("\n".join(lines))
        return resp

    return wrapper


def create_file_tree(
    *,
    project_root: Path,
    file_paths: set[Path],
    limit_depth_from_root: int | None = None,
    filter_: None | list[str] = None,
) -> dict[str, Any] | None:
    """Create a tree structure from a set of file and directory paths.

    This is intended to be returned by a tool function, for consumption
    by an LLM. It's intended to be a relatively "compact" representation
    of a file tree, to reduce token usage.

    Args:
        project_root: The root directory of the project.
        file_paths: Paths to **potentially** include in the tree.
        limit_depth_from_root: If provided, the tree will be truncated at this
            depth from the root directory. TODO: examples of different values.
        filter_: If provided, only paths that match the filter will be included
            in the tree. None matches all paths. str matches if the path contains
            the string. list[str] matches if the path contains any of the strings
            in the list.

    Returns:
        A dictionary representing the tree structure where:
        - Directories have a "f" key with either "..." or a list of filenames
        - The structure preserves the hierarchy of directories
        - Or None if no paths were included in the tree
    """
    file_paths = deepcopy(file_paths)  # Avoid mutation shenanigans
    project_root = project_root.absolute()

    # Make sure empty dirs aren't ignored
    dir_paths = set()
    for file_path in file_paths:
        for parent_path in file_path.parents:
            if parent_path == project_root:
                break
            dir_paths.add(parent_path)

    def _include_path(path_: Path) -> bool:
        return matches_filter(filter_, str(path_)) and (
            limit_depth_from_root is None
            or _get_depth_from_root(project_root, path_) <= limit_depth_from_root
        )

    dir_paths = {x for x in dir_paths if _include_path(x)}
    file_paths = {x for x in file_paths if _include_path(x)}

    sorted_dir_paths = sorted(dir_paths, key=lambda x: len(x.parts))
    sorted_file_paths = sorted(file_paths, key=lambda x: len(x.parts))

    default_data = {"root": {"f": "..."}}
    data: dict[str, Any] = deepcopy({"root": {"f": "..."}})

    for dir_path in sorted_dir_paths:
        # print(dir_path.relative_to(project_root))
        rel_parts = dir_path.relative_to(project_root).parts
        parent = data["root"]
        if len(rel_parts) == 0:
            continue  # This is the root dir?
        for rel_part in rel_parts:
            if rel_part not in parent:
                parent[rel_part] = {"f": "..."}
            parent = parent[rel_part]
    for file_path in sorted_file_paths:
        rel_parts = file_path.relative_to(project_root).parts
        parent = data["root"]
        if len(rel_parts) == 0:
            continue  # This is the root dir?
        for rel_part in rel_parts[:-1]:
            if rel_part not in parent:
                parent[rel_part] = {"f": []}
            parent = parent[rel_part]
        if parent["f"] == "...":
            parent["f"] = []
        parent["f"].append(file_path.name)
        parent["f"] = sorted(parent["f"])

    # Round trip through JSON just to sort things thank you
    data_jsonable = to_jsonable_python(data)
    data = json.loads(json.dumps(data_jsonable, sort_keys=True))

    if data == default_data:
        return None
    return data


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
