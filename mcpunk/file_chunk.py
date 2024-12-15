import enum
import logging
from hashlib import sha256
from typing import Literal, assert_never, get_args

from pydantic import (
    BaseModel,
    Field,
)

from mcpunk.util import matches_filter

logger = logging.getLogger(__name__)


class ChunkCategory(enum.StrEnum):
    callable = "callable"
    markdown_section = "markdown section"
    imports = "imports"
    module_level = "module_level"
    whole_file = "whole_file"
    other = "other"


# Seems if you annotate a FastMCP tool function with an enum it totally
# crashes claude desktop. So define an equivalent Literal type here.
ChunkCategoryLiteral = Literal[
    "callable",
    "markdown section",
    "imports",
    "module_level",
    "whole_file",
    "other",
]
assert set(get_args(ChunkCategoryLiteral)) == set(ChunkCategory.__members__.values())


class Chunk(BaseModel):
    """A chunk of a file, e.g. a function or a markdown section."""

    category: ChunkCategory = Field(description="`function`, `markdown section`, `imports`")
    name: str = Field(description="`my_function` or `MyClass` or `# My Section`")
    line: int | None = Field(description="Line within file where it starts. First line is 1.")
    content: str = Field(description="Content of the chunk")

    @property  # Consider caching
    def id_(self) -> str:
        """Generate a (probably) unique ID based on content, name, line, and category.

        This approach means that the ID will stay the same even if the chunk is recreated
        (e.g. as opposed to a totally random ID).
        There's chance of ids being duplicated, especially across files.
        The id includes the chunk name, which makes debugging and monitoring of tool
        requests far nicer.
        """
        components = [self.content, self.name, str(self.line), str(self.category)]
        return self.name + "_" + sha256("".join(components).encode()).hexdigest()[:10]

    def matches_filter(
        self,
        filter_: None | list[str],
        filter_on: Literal["name", "content", "name_or_content"],
    ) -> bool:
        """Return True if the chunk's name matches the given filter.

        str matches if the chunk's name contains the string.
        list[str] matches if the chunk's name contains any of the strings in the list.
        None matches all chunks.
        """
        if filter_on == "name":
            data = self.name
        elif filter_on == "content":
            data = self.content
        elif filter_on == "name_or_content":
            data = self.content + self.name
        else:
            assert_never(filter_on)
        return matches_filter(filter_, data)
