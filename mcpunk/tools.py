import json
import logging
import pathlib
import textwrap
from collections.abc import Sequence
from typing import Annotated, Any, Literal, Self

import mcp.types as mcp_types
from fastmcp import FastMCP
from pydantic import (
    BaseModel,
    Field,
    model_validator,
)
from pydantic_core import to_jsonable_python

from mcpunk import db
from mcpunk.dependencies import deps
from mcpunk.file_breakdown import (
    File,
)
from mcpunk.file_breakdown import (
    Project as FileBreakdownProject,
)
from mcpunk.file_chunk import (
    Chunk,
)
from mcpunk.git_analysis import get_recent_branches
from mcpunk.util import create_file_tree, log_inputs

logger = logging.getLogger(__name__)

PROJECTS: dict[str, "ToolProject"] = {}


mcp = FastMCP("Code Analysis")

ToolResponseSingleItem = mcp_types.TextContent | mcp_types.ImageContent | mcp_types.EmbeddedResource
ToolResponseSequence = Sequence[ToolResponseSingleItem]
ToolResponse = ToolResponseSequence | ToolResponseSingleItem
FilterType = Annotated[
    str | list[str] | None,
    Field(description="Match if any of these strings appear. Match all if None/null."),
]


class ToolProject(BaseModel):
    """A project containing files split into chunks and so on.

    These are created by the `configure_project` tool, and can be referenced by name
    (which is the key in the `PROJECTS` global dict) when calling other tools.
    """

    chunk_project: FileBreakdownProject

    # These are the chunks that the LLM has been told about through tool
    # requests. If an LLM tries to get info about a chunk that isn't in here
    # it means it's just guessing - which is likes to do. So you might want to
    # just say "hey buddy try asking about what chunks are available first".
    # TODO: make this redundant, perhaps force chunks to be fetched by a random-ish
    #       id which can only be known by listing chunks.
    llm_known_chunks: list[Chunk] = []

    @property
    def root(self) -> pathlib.Path:
        return self.chunk_project.root

    @property
    def git_path(self) -> pathlib.Path:
        if str(self.root).endswith(".git"):
            git_dir_path = self.root
        else:
            git_dir_path = self.root / ".git"
        if not git_dir_path.exists():
            raise ValueError(f"git dir not found at {git_dir_path}")
        return git_dir_path


class ProjectFile(BaseModel):
    project_name: str
    rel_path: Annotated[pathlib.Path, Field(description="Relative to project root")]

    @property
    def project(self) -> ToolProject:
        return _get_project_or_error(self.project_name)

    @property
    def abs_path(self) -> pathlib.Path:
        return self.project.chunk_project.root / self.rel_path

    @property
    def file(self) -> File:
        abs_path = self.abs_path
        matching_files = [f for f in self.project.chunk_project.files if f.abs_path == abs_path]
        if len(matching_files) != 1:
            raise ValueError(f"File {self.abs_path} not found in project {self.project_name}")
        return matching_files[0]

    @model_validator(mode="after")
    def validate_misc(self) -> Self:
        assert self.project is not None
        assert self.file is not None
        return self


class MCPToolOutput(BaseModel):
    """The output of a tool.

    You can specify any of the items in here, and they will all be rendered and
    returned to the client. If you specify NOTHING then the default response
    will be returned.
    """

    is_error: bool = False
    # Anything that pydantic core to_jsonable_python can handle - that's a lot of stuff!
    jsonable: Any | None = None
    raw: ToolResponse | None = None
    text: str | None = None

    # You might like this set to 2/4 for debugging, makes things look nice!
    # But that means more token usage I guess.
    # an int will do what you expect. None for compact. "default" will use
    # Whatever is set as the default on `MCPTools`
    indent: int | Literal["no_indent"] = Field(
        default_factory=lambda: deps.settings().default_response_indent,
    )

    default_response: str = "No response provided. This is not an error."

    # If the sum of the length of all text responses is greater than this
    # then an error will be returned to the caller. non-text responses (image, etc)
    # are not counted.
    max_chars: int = 20_000

    def render(self) -> ToolResponse:
        indent: int | None
        if self.indent == "no_indent":
            indent = None
        else:
            assert isinstance(self.indent, int)
            indent = self.indent
        assert indent is None or isinstance(indent, int)

        out: list[ToolResponseSingleItem] = []
        if self.is_error:
            out.append(mcp_types.TextContent(type="text", text="An error occurred."))
        if self.jsonable is not None:
            logger.debug(
                "Jsonable response\n"
                + textwrap.indent(json.dumps(to_jsonable_python(self.jsonable), indent=2), "    "),
            )
            out.append(
                mcp_types.TextContent(
                    type="text",
                    text=json.dumps(to_jsonable_python(self.jsonable), indent=indent),
                ),
            )
        if self.raw is not None:
            if isinstance(self.raw, ToolResponseSingleItem):
                out.append(self.raw)
            else:
                out.extend(self.raw)
        if self.text is not None:
            out.append(mcp_types.TextContent(type="text", text=self.text))
        if len(out) == 0:
            # Use default response if no data was provided
            assert not self.is_error  # Don't want to say there's an error if there was!
            out.append(mcp_types.TextContent(type="text", text=self.default_response))

        total_chars = sum(len(x.text) for x in out if isinstance(x, mcp_types.TextContent))
        if total_chars > self.max_chars:
            msg = (
                f"Response is {total_chars} chars which exceed the maximum allowed "
                f"of {self.max_chars}. Please adjust your request and try again."
            )
            logger.warning(msg)
            out = [mcp_types.TextContent(type="text", text=msg)]

        if deps.settings().include_chars_in_response:
            out.insert(
                0,
                mcp_types.TextContent(type="text", text=f"Response is {total_chars} chars"),
            )

        final_out: ToolResponse
        if len(out) == 1:
            final_out = out[0]
        else:
            final_out = out
        # logger.debug(f"Response {final_out}")
        logger.debug(
            "Final response\n"
            + textwrap.indent(json.dumps(to_jsonable_python(final_out), indent=2), "    "),
        )
        return final_out


@mcp.prompt()
@log_inputs
def dummy_prompt() -> str:
    return "Hey"


@mcp.resource("dummy://dummy")
@log_inputs
def dummy_resource() -> str:
    return "Hi"


@mcp.tool()
@log_inputs
def get_a_joke(
    animal: Annotated[
        str,
        Field(max_length=20),
    ],
) -> ToolResponse:
    """Get a really funny joke!"""
    return MCPToolOutput(
        text=(
            f"Why did the {animal} cross the road?\n"
            f"To get to the other side!\n"
            f"Because it was a {animal}."
        ),
    ).render()


@mcp.tool()
@log_inputs
def configure_project(
    root_path: Annotated[pathlib.Path, Field(description="Root path of the project")],
    project_name: Annotated[
        str,
        Field(
            description=(
                "Name of the project, for you to pick buddy, "
                "something short and sweet and memorable and unique"
            ),
        ),
    ],
) -> ToolResponse:
    """Configure a new project containing files.

    These files are split into 'chunks', which can be explored with the other tools.
    For example, a chunk might be a function, or a markdown section, or all imports
     in a file. A chunk name will be like `my_function` or `My Class` or `# My Section`.
    The contents will be the code itself starting with `def ...` or `class ...` or
    `# My Section` etc.
    Use ~ literally if the user specifies it.
    """
    path = root_path.expanduser().absolute()
    if project_name in PROJECTS:
        raise ValueError(f"Project {project_name} already exists")
    project = ToolProject(chunk_project=FileBreakdownProject.from_root_dir(path))
    PROJECTS[project_name] = project
    return MCPToolOutput(
        text=f"Project {path} configured with {len(project.chunk_project.files)} files",
    ).render()


@mcp.tool()
@log_inputs
def list_files_in_project(
    project_name: str,
    name_filter: Annotated[
        str | None | list[str],
        Field(
            description=(
                "Filter files by name. If None, all files are returned. "
                "If not None, only files whose name contains this string are returned. "
                "If a list, only files whose name contains any of the strings in the list "
                "are returned."
            ),
        ),
    ] = None,
    limit_depth_from_root: Annotated[
        int | None,
        Field(
            description=(
                "Limit the depth of the search to this many directories from the root. "
                "Start with 1."
                "If None, search all directories from the root."
            ),
        ),
    ] = None,
) -> ToolResponse:
    """List all files in a project.

    A project may have many files, so you are suggested
    to start with a depth limit to get an overview, and then continue increasing
    the depth limit plus a filter to filter to paths in specific subdirectories.
    """
    project = _get_project_or_error(project_name)
    data = create_file_tree(
        project_root=project.root,
        paths={x.abs_path for x in project.chunk_project.files},
        expand_parent_directories=True,
        limit_depth_from_root=limit_depth_from_root,
        filter_=name_filter,
    )
    if data is None:
        return MCPToolOutput(text="No paths").render()
    else:
        return MCPToolOutput(jsonable=data).render()


@mcp.tool()
@log_inputs
def list_files_by_chunk_name(
    project_name: str,
    filter_: FilterType,
) -> ToolResponse:
    """List all files containing any chunk with specified type, and name matching filter"""
    return _filter_files_by_chunk(project_name, filter_, "name").render()


@mcp.tool()
@log_inputs
def list_files_by_chunk_contents(
    project_name: str,
    filter_: FilterType,
) -> ToolResponse:
    """List all files containing any chunk with specified type, and contents matching filter"""
    return _filter_files_by_chunk(project_name, filter_, "name_or_content").render()


@mcp.tool()
@log_inputs
def list_all_chunk_meta_in_file(
    proj_file: ProjectFile,
) -> ToolResponse:
    """List chunk names in a specific file"""
    return _list_chunks_in_file(proj_file, None, "name").render()


@mcp.tool()
@log_inputs
def list_all_chunk_meta_in_file_where_contents_match(
    proj_file: ProjectFile,
    filter_: FilterType,
) -> ToolResponse:
    """List chunk names in a specific file where the contents match given filter"""
    return _list_chunks_in_file(proj_file, filter_, "name_or_content").render()


@mcp.tool()
@log_inputs
def chunk_details(
    proj_file: ProjectFile,
    chunk_name: Annotated[
        str,
        Field(
            description=(
                "You must already know the chunk name, do not guess it. It can be found "
                f"via the {list_all_chunk_meta_in_file.__name__} tool. The chunk "
                f"name provided here must match the chunk name in the "
                f"{list_all_chunk_meta_in_file_where_contents_match.__name__} tool exactly."
            ),
        ),
    ],
) -> ToolResponse:
    """Full contents of a specific chunk.

    To use this you must first know the file and chunk name, which you can find from
    tools like `list_chunks_in_file`.
    """
    target_file = proj_file.file
    chunks = [chunk for chunk in target_file.chunks if chunk.name == chunk_name]
    if len(chunks) == 0:
        return MCPToolOutput(
            text=(
                f"No matching chunks. Please use the {list_all_chunk_meta_in_file.__name__} tool "
                f"to find available chunks."
            ),
        ).render()

    chunks = [chunk for chunk in chunks if chunk in proj_file.project.llm_known_chunks]
    if len(chunks) == 0:
        return MCPToolOutput(
            text=(
                f"Chunk(s) found, but it's not a chunk that has been listed through the "
                f"{list_all_chunk_meta_in_file.__name__} tool. use that tool to list the chunk "
                f"and ensure you are aware of it before asking for its details. "
            ),
        ).render()
    return MCPToolOutput(jsonable=[x.content for x in chunks]).render()


@mcp.tool()
@log_inputs
def list_most_recently_checked_out_branches(
    project_name: str,
    n: Annotated[int, Field(ge=20, le=50)] = 20,
) -> ToolResponse:
    """List the n most recently checked out branches in the project"""
    project = _get_project_or_error(project_name)
    return MCPToolOutput(jsonable=get_recent_branches(project.git_path, n)).render()


@mcp.tool()
@log_inputs
def diff_with_ref(
    project_name: str,
    ref: Annotated[str, Field(max_length=100)],
) -> ToolResponse:
    """Return a summary of the diff between HEAD the given ref.

    You probably want the ref  to be the 'base' branch like develop or main, off which
    PRs are made - and you can likely determine this by viewing the most recently
    checked out branches.
    """
    project = _get_project_or_error(project_name)
    from git import Repo

    repo = Repo(project.git_path)
    # head = repo.head.commit
    # compare_from = repo.commit(ref)
    # diffs = compare_from.diff(head, create_patch=True)
    # print(repo.git.diff(f"{ref}s...HEAD", ignore_blank_lines=True, ignore_space_at_eol=True))
    diff = repo.git.diff(
        f"{ref}...HEAD",
        ignore_blank_lines=True,
        ignore_space_at_eol=True,
    )  # create_patch=True)
    return MCPToolOutput(jsonable=diff, max_chars=50_000).render()


@mcp.tool()
@log_inputs
def add_tasks(
    task_actions: Annotated[list[str], Field(min_length=1, max_length=10)],
    common_prefix: str | None = None,
) -> ToolResponse:
    """Add tasks to be completed by an LLM in the future.

    Do not add a task unless explicitly instructed to do so.

    When adding tasks, provide all required context.
    For example: step 1 set up the ~/git/p1 and ~/git/p2 repos projects step 2 load the diff with
        ref develop step 3 confirm that the function added in /examples/script.py is
        consistent with the existing /examples/other_script.py file.
    The common_prefix is prefixed to each task's action (if not None), it's provided
    to avoid having to repeat the common context for each task.

    Call this tool multiple times to add many tasks.
    """
    if common_prefix is not None:
        task_actions = [f"{common_prefix} {action}" for action in task_actions]

    with db.get_task_manager() as task_manager:
        for task_action in task_actions:
            task_manager.add_task(task_action)
    return MCPToolOutput(text="ok").render()


@mcp.tool()
@log_inputs
def get_task() -> ToolResponse:
    """Get a single task.

    After you complete the task, mark it as done by calling the `set_task_done` tool.
    """
    with db.get_task_manager() as task_manager:
        db_task = task_manager.get_task()
        if db_task is None:
            return MCPToolOutput(text="no tasks").render()
        return MCPToolOutput(
            jsonable={
                "action": db_task.action,
                "id": db_task.id,
            },
        ).render()


@mcp.tool()
@log_inputs
def mark_task_done(
    task_id: int,
    outcome: str,
    # Type hinting with `db.TaskFollowUpCriticality` directly seems to completely FRY
    # claude desktop - seems the schema it generates perhaps causes it to generate
    # invalid input data and crashes (?) the desktop app before it even sends any
    # data. So reproduce it as a Literal 🐀
    follow_up_criticality: Annotated[
        Literal["no_followup", "low", "medium", "high"],
        Field(description="If the task requires no follow up, set to no_followup"),
    ],
) -> ToolResponse:
    """Set a task as done wth a specific outcome.

    You can call this multiple times to update the outcome.
    """
    allowed_vals = {str(x) for x in db.TaskFollowUpCriticality.__members__.values()}
    if follow_up_criticality not in allowed_vals:
        raise ValueError(f"{follow_up_criticality} must be in {allowed_vals}")
    with db.get_task_manager() as task_manager:
        task_manager.set_task_done(
            task_id,
            outcome,
            db.TaskFollowUpCriticality(follow_up_criticality),
        )
    return MCPToolOutput(text="ok").render()


def _get_project_or_error(project_name: str) -> ToolProject:
    if project_name not in PROJECTS:
        raise ValueError(
            f"Project {project_name} not configured. Either double check the project name "
            f"or run the tool to set up a new project. The server may have been restarted "
            f"causing it to no longer be configured.",
        )
    return PROJECTS[project_name]


def _list_chunks_in_file(
    proj_file: ProjectFile,
    filter_: FilterType,
    filter_on: Literal["name", "name_or_content"],
) -> MCPToolOutput:
    target_file = proj_file.file
    chunks = [x for x in target_file.chunks if x.matches_filter(filter_, filter_on)]
    proj_file.project.llm_known_chunks.extend(chunks)

    resp_data = [{"n": x.name, "t": x.category} for x in chunks]

    return MCPToolOutput(
        jsonable=[
            f"{len(chunks)} of {len(target_file.chunks)}",
            resp_data,
        ],
    )


def _filter_files_by_chunk(
    project_name: str,
    filter_: FilterType,
    filter_on: Literal["name", "name_or_content"],
) -> MCPToolOutput:
    project = _get_project_or_error(project_name)
    matching_files: set[pathlib.Path] = set()
    for file in project.chunk_project.files:
        if any(c.matches_filter(filter_, filter_on) for c in file.chunks):
            matching_files.add(file.abs_path)
    data = create_file_tree(project_root=project.root, paths=matching_files)
    if data is None:
        return MCPToolOutput(text="No files found")
    return MCPToolOutput(jsonable=data)


if __name__ == "__main__":
    # mark_task_done(task_id=10, outcome="ok", follow_up_criticality="low")
    configure_project(
        root_path=pathlib.Path("~/git/mcpunk"),
        project_name="mcpunk",
    )
    print()
    _proj = PROJECTS["mcpunk"].chunk_project
    print(len([f for f in _proj.files if f.ext == ".py"]), "files")
    print(sum(len(f.contents.splitlines()) for f in _proj.files if f.ext == ".py"), "lines")
    print(sum(len(f.contents) for f in _proj.files if f.ext == ".py"), "chars")
    list_files_by_chunk_contents(
        project_name="mcpunk",
        filter_="desktop",
    )
    _list_chunks_in_file(
        proj_file=ProjectFile(
            project_name="mcpunk",
            rel_path=pathlib.Path("README.md"),
        ),
        filter_=None,
        filter_on="name",
    )
    chunk_details(
        proj_file=ProjectFile(
            project_name="mcpunk",
            rel_path=pathlib.Path("README.md"),
        ),
        chunk_name="Development",
    )
    # f = [
    #     x
    #     for x in PROJECTS["mcpunk"].chunk_project.files
    #     if x.abs_path == pathlib.Path(PROJECTS["mcpunk"].root / "docs/infrastructure.md")
    # ][0]
    diff_with_ref(
        project_name="mcpunk",
        ref="main",
    )
