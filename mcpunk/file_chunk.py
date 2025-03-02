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
        filter_: None | list[str] | str,
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

    def split(
        self,
        max_size: int = 10_000,
        split_chunk_prefix: str = (
            "[This is a subsection of the chunk. Other parts contain the rest of the chunk]\n\n"
        ),
    ) -> list["Chunk"]:
        """Split this chunk into smaller chunks.

        This will split the chunk at line boundaries, unless the
        line is already longer than max_size.

        Args:
            max_size: Maximum size in characters for the chunk contents. At least 100.
            split_chunk_prefix: Prefix to add the start of each newly created split chunk.
                Unused if the chunk is not split. You can set to empty string to
                suppress the prefix.

        Returns:
            List containing either the original chunk (if small enough) or multiple smaller chunks
        """
        assert max_size >= 100, "max_size must be at least 100"
        # If chunk is small enough, return it as is
        if len(self.content) <= max_size:
            return [self]
        max_size -= len(split_chunk_prefix)

        result: list[Chunk] = []
        max_line_size = max_size - 50  # Leave some margin

        # Preprocess to split long lines first. This could be avoided, but it does
        # make the whole thing a bit simpler as we always know later on that a single line
        # will never be longer than max_size.
        processed_lines = []
        for line in self.content.splitlines(keepends=True):
            if len(line) > max_line_size:
                # Split the line into chunks of max_line_size
                for i in range(0, len(line), max_line_size):
                    processed_lines.append(line[i : i + max_line_size])
            else:
                processed_lines.append(line)

        # Now split into chunks of max_size
        current_content: list[str] = []
        current_size = 0
        part_num = 1

        for line in processed_lines:
            # If adding this line would exceed the limit, create a new chunk
            if current_size + len(line) > max_size and current_content:
                new_chunk = Chunk(
                    category=self.category,
                    name=f"{self.name}_part{part_num}",
                    content=split_chunk_prefix + "".join(current_content),
                    line=None,
                )
                result.append(new_chunk)
                part_num += 1
                current_content = []
                current_size = 0

            # Add the line to the current chunk
            current_content.append(line)
            current_size += len(line)

        # Add the final chunk if there's anything left
        if current_content:
            new_chunk = Chunk(
                category=self.category,
                name=f"{self.name}_part{part_num}",
                content=split_chunk_prefix + "".join(current_content),
                line=None,
            )
            result.append(new_chunk)

        return result
