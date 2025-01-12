from pathlib import Path

from mcpunk.file_chunkers import WholeFileChunker


def test_whole_file_chunker() -> None:
    source_code = "some\ncontent"

    chunks = WholeFileChunker(source_code, Path("test.txt")).chunk_file()

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.category.value == "whole_file"
    assert chunk.name == "<whole_file>"
    assert chunk.line == 1
    assert chunk.content == "some\ncontent"

    # Accepts any file
    assert WholeFileChunker.can_chunk("", Path("whatever.txt"))
    assert WholeFileChunker.can_chunk("", Path("test.xyz"))
