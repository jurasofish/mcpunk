from pathlib import Path

from mcpunk.file_chunkers import MarkdownChunker


def test_markdown_chunker() -> None:
    source_code = """\
Pre-header content

# Section 1
Some content

## Subsection 1.1
More content
More lines

# Section 2
Final content
"""
    assert MarkdownChunker.can_chunk("", Path("test.md"))
    assert not MarkdownChunker.can_chunk("", Path("test.txt"))

    chunks = MarkdownChunker(source_code, Path("test.md")).chunk_file()
    chunks = sorted(chunks, key=lambda x: x.line if x.line is not None else -1)

    assert [x.name for x in chunks] == ["(no heading)", "Section 1", "Subsection 1.1", "Section 2"]

    # Test categories
    assert all(x.category.value == "markdown section" for x in chunks)

    # Test line numbers
    assert chunks[0].line == 1  # No heading section
    assert chunks[1].line == 3  # Section 1
    assert chunks[2].line == 6  # Subsection 1.1
    assert chunks[3].line == 10  # Section 2

    # Test content
    assert chunks[0].content == "Pre-header content\n"
    assert chunks[1].content == "# Section 1\nSome content\n"
    assert chunks[2].content == "## Subsection 1.1\nMore content\nMore lines\n"
    assert chunks[3].content == "# Section 2\nFinal content\n"
