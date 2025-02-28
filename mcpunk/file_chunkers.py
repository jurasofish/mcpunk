from abc import abstractmethod
from pathlib import Path

from bs4 import BeautifulSoup

from mcpunk.file_chunk import Chunk, ChunkCategory
from mcpunk.python_file_analysis import Callable, extract_imports, extract_module_statements


class BaseChunker:
    """Base class for file chunkers."""

    def __init__(self, source_code: str, file_path: Path) -> None:
        self.source_code = source_code
        self.file_path = file_path

    @staticmethod
    @abstractmethod
    def can_chunk(source_code: str, file_path: Path) -> bool:
        """Return True if the file can likely be chunked by this class.

        This should be a very quick cheap check, quite possibly just using the file
        extension. Do not assume that the file exists on disk.

        Users of file chunks should handle gracefully the case where this returns
        True but `chunk_file` fails. For example, the file may appear to be Python
        but could contain invalid syntax.
        """
        raise NotImplementedError

    @abstractmethod
    def chunk_file(self) -> list[Chunk]:
        """Chunk the given file."""
        raise NotImplementedError


class WholeFileChunker(BaseChunker):
    """Chunk the file into segments of at most 10000 characters, splitting at line boundaries."""

    MAX_CHUNK_SIZE: int = 10000
    MAX_LINE_SIZE: int = 9950  # Slightly smaller to ensure we don't exceed MAX_CHUNK_SIZE

    @staticmethod
    def can_chunk(source_code: str, file_path: Path) -> bool:  # noqa: ARG004
        return True

    def chunk_file(self) -> list[Chunk]:
        # Pre-process any lines exceeding MAX_LINE_SIZE
        processed_lines = self._preprocess_long_lines(self.source_code, self.MAX_LINE_SIZE)
        chunks: list[Chunk] = []

        current_chunk: list[str] = []
        current_size: int = 0
        line_num: int = 1
        chunk_start_line: int = 1

        for line in processed_lines:
            # If adding this line would exceed the limit, create a new chunk
            if current_size + len(line) > self.MAX_CHUNK_SIZE and current_chunk:
                chunks.append(
                    Chunk(
                        category=ChunkCategory.whole_file,
                        name=f"file_chunk_{chunk_start_line}",
                        content="".join(current_chunk),
                        line=chunk_start_line,
                    ),
                )

                # Reset for next chunk
                current_chunk = []
                current_size = 0
                chunk_start_line = line_num

            # Add the line to the current chunk
            current_chunk.append(line)
            current_size += len(line)
            line_num += 1

        # Add the final chunk if there's anything left
        if current_chunk:
            chunks.append(
                Chunk(
                    category=ChunkCategory.whole_file,
                    name=f"<file_chunk_{chunk_start_line}>",
                    content="".join(current_chunk),
                    line=chunk_start_line,
                ),
            )

        return chunks

    @staticmethod
    def _preprocess_long_lines(source_code: str, max_line_size: int = 9950) -> list[str]:
        """Split any lines longer than MAX_LINE_SIZE into multiple lines."""
        original_lines = source_code.splitlines(keepends=True)
        processed_lines = []

        for line in original_lines:
            if len(line) > max_line_size:
                # Split the line into chunks of MAX_LINE_SIZE
                for i in range(0, len(line), max_line_size):
                    chunk = line[i : i + max_line_size]
                    processed_lines.append(chunk)
            else:
                processed_lines.append(line)

        return processed_lines


class PythonChunker(BaseChunker):
    @staticmethod
    def can_chunk(source_code: str, file_path: Path) -> bool:  # noqa: ARG004
        return str(file_path).endswith(".py")

    def chunk_file(self) -> list[Chunk]:
        callables = Callable.from_source_code(self.source_code)
        imports = "\n".join(extract_imports(self.source_code))
        module_level_statements = "\n".join(extract_module_statements(self.source_code))

        chunks: list[Chunk] = []

        if imports.strip() != "":
            chunks.append(
                Chunk(category=ChunkCategory.imports, name="imports", line=None, content=imports),
            )
        if module_level_statements.strip() != "":
            chunks.append(
                Chunk(
                    category=ChunkCategory.module_level,
                    name="module_level_statements",
                    line=None,
                    content=module_level_statements,
                ),
            )

        chunks.extend(
            Chunk(
                category=ChunkCategory.callable,
                name=callable_.name,
                line=callable_.line,
                content=callable_.code,
            )
            for callable_ in callables
        )
        return chunks


class MarkdownChunker(BaseChunker):
    @staticmethod
    def can_chunk(source_code: str, file_path: Path) -> bool:  # noqa: ARG004
        return str(file_path).endswith(".md")

    def chunk_file(self) -> list[Chunk]:
        chunks: list[Chunk] = []
        current_section: list[str] = []
        current_heading: str | None = None
        current_line = 1
        start_of_section = 1

        for line in self.source_code.split("\n"):
            if line.startswith("#"):
                # If we have a previous section, save it
                if current_section:
                    chunks.append(
                        Chunk(
                            category=ChunkCategory.markdown_section,
                            name=current_heading.replace("#", "").strip()
                            if current_heading is not None
                            else "(no heading)",
                            line=start_of_section,
                            content="\n".join(current_section),
                        ),
                    )
                current_heading = line
                current_section = [line]
                start_of_section = current_line
            else:
                current_section.append(line)
            current_line += 1

        # Add the last section
        if current_section:
            chunks.append(
                Chunk(
                    category=ChunkCategory.markdown_section,
                    name=current_heading.replace("#", "").strip()
                    if current_heading is not None
                    else "(no heading)",
                    line=start_of_section,
                    content="\n".join(current_section),
                ),
            )

        return chunks


class VueChunker(BaseChunker):
    """Chunks Vue Single File Components into their constituent blocks.

    Intention is to put template, script, style (and other custom) blocks
    into their own chunks.
    See https://vuejs.org/api/sfc-spec
    """

    @staticmethod
    def can_chunk(source_code: str, file_path: Path) -> bool:  # noqa: ARG004
        return str(file_path).endswith(".vue")

    def chunk_file(self) -> list[Chunk]:
        # To preserve whitespace, we wrap the source code in a <pre> tag.
        # Without this, BeautifulSoup will strip/fiddle whitespace.
        # See https://stackoverflow.com/a/33788712
        soup_with_pre = BeautifulSoup(
            "<pre>" + self.source_code + "</pre>",
            "html.parser",
        )
        soup_within_pre = soup_with_pre.pre
        chunks: list[Chunk] = []

        # Find all top-level blocks. These are typcially template, script, style,
        # plus any custom blocks.
        top_level_elements = soup_within_pre.find_all(recursive=False)
        for element in top_level_elements:
            chunks.append(
                Chunk(
                    category=ChunkCategory.other,
                    name=element.name,
                    content=str(element),
                    line=element.sourceline,
                ),
            )

        # Get content not in any tag, aggressively stripping whitespace.
        # I'm not sure if it's actually valid to have content outside a <something>
        # tag but whatever doesn't hurt to grab it.
        outer_content_items: list[str] = []
        for outer_content_item in soup_within_pre.find_all(string=True, recursive=False):
            if outer_content_item.strip():
                outer_content_items.append(str(outer_content_item).strip())
        if outer_content_items:
            chunks.append(
                Chunk(
                    category=ChunkCategory.module_level,
                    name="outer_content",
                    content="\n".join(outer_content_items),
                    line=None,
                ),
            )

        return chunks
