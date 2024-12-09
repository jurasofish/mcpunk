from abc import abstractmethod
from pathlib import Path

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


class PythonChunker(BaseChunker):
    @staticmethod
    def can_chunk(source_code: str, file_path: Path) -> bool:  # noqa: ARG004
        return str(file_path).endswith(".py")

    def chunk_file(self) -> list[Chunk]:
        callables = Callable.from_source_code(self.source_code)
        imports = "\n".join(extract_imports(self.source_code))
        module_level_statements = "\n".join(extract_module_statements(self.source_code))
        chunks: list[Chunk] = [
            Chunk(category=ChunkCategory.imports, name="<imports>", line=None, content=imports),
            Chunk(
                category=ChunkCategory.module_level,
                name="<module_level_statements>",
                line=None,
                content=module_level_statements,
            ),
        ]
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
        current_section = []
        current_heading = None
        current_line = 1

        for line in self.source_code.split("\n"):
            if line.startswith("#"):
                # If we have a previous section, save it
                if current_heading is not None:
                    chunks.append(
                        Chunk(
                            category=ChunkCategory.markdown_section,
                            name=current_heading.replace("#", "").strip(),
                            line=current_line - len(current_section),
                            content="\n".join(current_section),
                        ),
                    )
                current_heading = line
                current_section = [line]
            else:
                current_section.append(line)
            current_line += 1

        # Add the last section
        if current_heading is not None:
            chunks.append(
                Chunk(
                    category=ChunkCategory.markdown_section,
                    name=current_heading.replace("#", "").strip(),
                    line=current_line - len(current_section),
                    content="\n".join(current_section),
                ),
            )
        # If there's content before any heading
        elif current_section:
            chunks.append(
                Chunk(
                    category=ChunkCategory.markdown_section,
                    name="(no heading)",
                    line=1,
                    content="\n".join(current_section),
                ),
            )

        return chunks
