import json
import logging
import random
from collections import defaultdict
from collections.abc import Callable
from copy import deepcopy
from functools import wraps
from pathlib import Path
from string import ascii_lowercase
from typing import Any, Literal, ParamSpec, TypeVar, assert_never

from pydantic_core import to_jsonable_python

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
    expand_parent_directories: bool = True,
    limit_depth_from_root: int | None = None,
    filter_: None | list[str] = None,
    force_response_structure: Literal["dict", "plain_text"] | None = None,
) -> dict[str, Any] | str | None:
    """Create a tree structure from a set of file and directory paths.

    This is intended to be returned by a tool function, for consumption
    by an LLM. It's intended to be a relatively "compact" representation
    of a file tree, to reduce token usage.

    Args:
        project_root: The root directory of the project.
        paths: Paths to **potentially** include in the tree.
        expand_parent_directories: If true, all directories between each file
            and the project root will be included in the tree. This avoids
            skipping directories that contain only files.
        limit_depth_from_root: If provided, the tree will be truncated at this
            depth from the root directory. TODO: examples of different values.
        filter_: If provided, only paths that match the filter will be included
            in the tree. None matches all paths. str matches if the path contains
            the string. list[str] matches if the path contains any of the strings
            in the list.
        force_response_structure: If provided, force the response to be a dict
            or a plain text string.

    Returns:
        EITHER:
            A dictionary representing the tree structure where:
                - Directories have a "f" key with either "..." or a list of filenames
                - The structure preserves the hierarchy of directories
                - Or None if no paths were included in the tree
            OR a string representing the tree structure in plain text.
            Whichever response has the fewest characters is returned, or whichever
            is dictated by `force_response_structure`.

    """
    paths = deepcopy(paths)  # Avoid mutation shenanigans
    project_root = project_root.absolute()

    # Make sure empty dirs aren't ignored
    if expand_parent_directories:
        new_dir_paths = set()
        for file_path in paths:
            for parent_path in file_path.parents:
                if parent_path == project_root:
                    break
                new_dir_paths.add(parent_path)
        paths = paths | new_dir_paths

    filtered_paths = {
        x
        for x in paths
        if matches_filter(filter_, str(x))
        and (
            limit_depth_from_root is None
            or _get_depth_from_root(project_root, x) <= limit_depth_from_root
        )
    }
    filtered_dir_paths = sorted(
        [x for x in filtered_paths if x.is_dir()],
        key=lambda x: len(x.parts),
    )
    filtered_file_paths = sorted(
        [x for x in filtered_paths if x.is_file()],
        key=lambda x: len(x.parts),
    )
    default_data = {"root": {"f": "..."}}
    data: dict[str, Any] = deepcopy({"root": {"f": "..."}})

    for dir_path in filtered_dir_paths:
        # print(dir_path.relative_to(project_root))
        rel_parts = dir_path.relative_to(project_root).parts
        parent = data["root"]
        if len(rel_parts) == 0:
            continue  # This is the root dir?
        for rel_part in rel_parts:
            if rel_part not in parent:
                parent[rel_part] = {"f": "..."}
            parent = parent[rel_part]
    for file_path in filtered_file_paths:
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

    # Round trip through JSON just to sort things like `Path('/x')` -> `/x` thank you
    data_jsonable = to_jsonable_python(data)
    data = json.loads(json.dumps(data_jsonable, sort_keys=True))

    if data == default_data:
        return None

    plain_text_version = ""
    for p in sorted(filtered_file_paths):
        plain_text_version += f"{p.relative_to(project_root)}\n"

    plain_text_version_v2 = ""
    files_by_parent_dir: dict[Path, list[Path]] = defaultdict(list)
    for p in sorted(filtered_file_paths):
        files_by_parent_dir[p.parent].append(p)
    for parent_dir in sorted(files_by_parent_dir.keys()):
        plain_text_version_v2 += f"{parent_dir.relative_to(project_root)}: "
        plain_text_version_v2 += "; ".join(x.name for x in files_by_parent_dir[parent_dir])
        plain_text_version_v2 += "\n"

    if len(plain_text_version_v2) < len(plain_text_version):
        plain_text_version = plain_text_version_v2

    if force_response_structure == "dict":
        return data
    elif force_response_structure == "plain_text":
        return plain_text_version
    elif force_response_structure is None:
        serialised_json_version = json.dumps(data, indent=2)
        logger.info(
            f"Serialised JSON version is {len(serialised_json_version)} "
            f"chars: {serialised_json_version}",
        )
        logger.info(
            f"Plain text version is {len(plain_text_version)} chars: {plain_text_version}",
        )
        if len(plain_text_version) < len(serialised_json_version):
            return plain_text_version
        else:
            return serialised_json_version
    else:
        assert_never(force_response_structure)


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
