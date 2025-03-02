from mcpunk.file_chunk import Chunk, ChunkCategory


def test_chunk_id_consistency() -> None:
    """Test that identical chunks produce the same ID."""
    chunk1 = Chunk(
        category=ChunkCategory.callable,
        name="test_func",
        line=10,
        content="def test_func():\n    return True",
    )
    chunk2 = Chunk(
        category=ChunkCategory.callable,
        name="test_func",
        line=10,
        content="def test_func():\n    return True",
    )
    assert chunk1.id_ == chunk2.id_


def test_chunk_id_uniqueness() -> None:
    """Test that different chunks produce different IDs."""
    chunk1 = Chunk(
        category=ChunkCategory.callable,
        name="func1",
        line=10,
        content="def func1():\n    return True",
    )
    chunk2 = Chunk(
        category=ChunkCategory.callable,
        name="func2",  # Different name
        line=10,
        content="def func1():\n    return True",
    )
    chunk3 = Chunk(
        category=ChunkCategory.callable,
        name="func1",
        line=20,  # Different line
        content="def func1():\n    return True",
    )
    chunk4 = Chunk(
        category=ChunkCategory.callable,
        name="func1",
        line=10,
        content="def func1():\n    return False",  # Different content
    )

    assert chunk1.id_ != chunk2.id_
    assert chunk1.id_ != chunk3.id_
    assert chunk1.id_ != chunk4.id_


def test_chunk_id_format() -> None:
    """Test that the ID follows the expected format: name_hash."""
    chunk = Chunk(
        category=ChunkCategory.callable,
        name="test_func",
        line=10,
        content="def test_func():\n    return True",
    )
    chunk_id = chunk.id_
    # ID should start with the chunk name followed by underscore
    assert chunk_id.startswith("test_func_")
    # The rest should be a 10-character hash
    hash_part = chunk_id[len("test_func_") :]
    assert len(hash_part) == 10
    # Hash should be hexadecimal (0-9, a-f)
    assert all(c in "0123456789abcdef" for c in hash_part)


def test_chunk_matches_filter_string_on_name() -> None:
    """Test that a string filter matches when present in chunk name."""
    chunk = Chunk(
        category=ChunkCategory.callable,
        name="test_function",
        line=1,
        content="def test_function():\n    pass",
    )
    assert chunk.matches_filter("function", "name") is True
    assert chunk.matches_filter("test", "name") is True
    assert chunk.matches_filter("test_function", "name") is True


def test_chunk_matches_filter_list_on_name() -> None:
    """Test that a list filter matches when any element is in chunk name."""
    chunk = Chunk(
        category=ChunkCategory.callable,
        name="test_function",
        line=1,
        content="def test_function():\n    pass",
    )
    assert chunk.matches_filter(["func", "other"], "name") is True
    assert chunk.matches_filter(["test", "xyz"], "name") is True
    assert chunk.matches_filter(["unrelated", "test_function"], "name") is True


def test_chunk_matches_filter_none() -> None:
    """Test that None filter matches all chunks."""
    chunk = Chunk(
        category=ChunkCategory.callable,
        name="test_function",
        line=1,
        content="def test_function():\n    pass",
    )
    assert chunk.matches_filter(None, "name") is True
    assert chunk.matches_filter(None, "content") is True
    assert chunk.matches_filter(None, "name_or_content") is True


def test_chunk_matches_filter_on_content() -> None:
    """Test filtering on content."""
    chunk = Chunk(
        category=ChunkCategory.callable,
        name="test_function",
        line=1,
        content="def test_function():\n    return 'hello world'",
    )
    assert chunk.matches_filter("hello", "content") is True
    assert chunk.matches_filter("return", "content") is True
    assert chunk.matches_filter(["world", "planet"], "content") is True
    assert chunk.matches_filter("not_present", "content") is False


def test_chunk_matches_filter_on_name_or_content() -> None:
    """Test filtering on both name and content combined."""
    chunk = Chunk(
        category=ChunkCategory.callable,
        name="example_function",
        line=1,
        content="def test_function():\n    return 'hello'",
    )
    assert chunk.matches_filter("example", "name_or_content") is True
    assert chunk.matches_filter("hello", "name_or_content") is True
    assert chunk.matches_filter("function", "name_or_content") is True


def test_chunk_matches_filter_non_matching() -> None:
    """Test various non-matching cases."""
    chunk = Chunk(
        category=ChunkCategory.callable,
        name="test_function",
        line=1,
        content="def test_function():\n    pass",
    )
    assert chunk.matches_filter("missing", "name") is False
    assert chunk.matches_filter(["absent", "not_here"], "name") is False
    assert chunk.matches_filter("return", "content") is False
    assert chunk.matches_filter("missing", "name_or_content") is False


def test_chunk_split_small_chunk_not_split() -> None:
    """Test that small chunks (below max_size) aren't split."""
    chunk = Chunk(
        category=ChunkCategory.callable,
        name="small_func",
        line=1,
        content="Small content that is definitely below default max_size",
    )
    result = chunk.split()
    assert len(result) == 1
    assert result[0] is chunk  # It should return the original object, not a copy


def test_chunk_split_at_line_boundaries() -> None:
    """Test that chunks are split at line boundaries when possible."""
    # Create multi-line content where each line is below max_line_size
    lines = [f"Line {i}" + "x" * 50 for i in range(20)]
    content = "\n".join(lines)
    chunk = Chunk(category=ChunkCategory.callable, name="multi_line_func", line=1, content=content)

    # Choose a max_size that will require splitting but allow multiple lines per chunk
    max_size = 300
    result = chunk.split(max_size=max_size, split_chunk_prefix="blah")

    assert len(result) > 1
    for chunk_idx, r in enumerate(result):
        assert len(r.content) <= max_size, f"Chunk {chunk_idx} exceeds max_size"

    prefix_len = len("blah")

    # Verify splits occur at line boundaries
    for i in range(len(result) - 1):  # Check all but the last chunk
        chunk_content = result[i].content[prefix_len:]
        # Each non-final chunk should end with a newline
        assert chunk_content.endswith("\n"), f"Chunk {i} doesn't end at a line boundary"

    # Verify no line is split across chunks (by checking each original line is fully in one chunk)
    for line in lines:
        # Count how many chunks contain this exact line (should be exactly 1)
        line_with_newline = line + "\n"
        found_in_chunks = 0
        for r in result:
            chunk_content = r.content[prefix_len:]
            if line_with_newline in chunk_content:
                found_in_chunks += 1

        # The last line doesn't have a newline
        if line == lines[-1]:
            line_no_newline = line
            for r in result:
                chunk_content = r.content[prefix_len:]
                if chunk_content.endswith(line_no_newline):
                    found_in_chunks += 1

        assert found_in_chunks == 1

    # The combined content (without prefixes) should match original content
    reconstructed = ""
    for r in result:
        reconstructed += r.content[prefix_len:]
    assert reconstructed == content


def test_chunk_split_very_long_single_line() -> None:
    """Test that very long single lines are split correctly."""
    long_line = "x" * 5000  # Single line, no newlines
    chunk = Chunk(category=ChunkCategory.callable, name="long_line_func", line=1, content=long_line)

    max_size = 1000
    result = chunk.split(max_size=max_size, split_chunk_prefix="blah")

    assert len(result) > 1, "Long line should be split into multiple chunks"

    for chunk_idx, r in enumerate(result):
        assert len(r.content) <= max_size, f"Chunk {chunk_idx} exceeds max_size"

    # The prefix length for first and subsequent chunks
    prefix_len = len("blah")

    # Reconstruct original content without prefixes
    reconstructed = ""
    for r in result:
        reconstructed += r.content[prefix_len:]

    assert reconstructed == long_line, "Reconstructed content doesn't match original"


def test_chunk_split_naming_convention() -> None:
    """Test that split chunks follow the expected naming convention."""
    chunk = Chunk(
        category=ChunkCategory.callable,
        name="original_name",
        line=1,
        content="\n".join(["x" * 100 for _ in range(10)]),  # Content that will be split
    )

    result = chunk.split(max_size=200)

    assert len(result) > 1, "Content should be split into multiple chunks"

    # Check naming pattern: original_name_part1, original_name_part2, etc.
    for i, r in enumerate(result, 1):
        assert r.name == f"original_name_part{i}", f"Incorrect name for chunk {i}"

    # Verify other properties are maintained or adjusted as expected
    for r in result:
        assert r.category == chunk.category, "Category should be preserved"
        assert r.line is None, "Line number should be None for split chunks"


def test_chunk_split_custom_prefix() -> None:
    """Test that custom prefixes are applied correctly to split chunks."""
    chunk = Chunk(
        category=ChunkCategory.callable,
        name="test_func",
        line=1,
        content="\n".join(["x" * 100 for _ in range(10)]),
    )

    # Test with custom prefix
    custom_prefix = "CUSTOM PREFIX: "
    result = chunk.split(max_size=200, split_chunk_prefix=custom_prefix)

    assert len(result) > 1, "Content should be split into multiple chunks"

    # Each chunk should start with the custom prefix
    for chunk_idx, r in enumerate(result):
        assert r.content.startswith(custom_prefix), f"Chunk {chunk_idx} doesn't have custom prefix"

    # Test with empty prefix
    empty_result = chunk.split(max_size=200, split_chunk_prefix="")

    # Chunks should start with content, not the default prefix
    for chunk_idx, r in enumerate(empty_result):
        assert r.content.startswith("x"), f"Chunk {chunk_idx} doesn't start with expected content"
        assert not r.content.startswith(
            "[This is",
        ), "Default prefix was used despite empty custom prefix"


def test_chunk_split_content_preservation() -> None:
    """Test that splitting preserves all original content."""
    # Create content with distinct lines for easier verification
    lines = [f"Line {i} with unique content" for i in range(20)]
    content = "\n".join(lines)
    chunk = Chunk(category=ChunkCategory.callable, name="test_func", line=1, content=content)

    # Use empty prefix to simplify content reconstruction
    result = chunk.split(max_size=300, split_chunk_prefix="")

    combined = "".join(r.content for r in result)

    # Should exactly match original content
    assert combined == content, "Content was not preserved during splitting"

    # Verify specific lines are preserved
    for i, line in enumerate(lines):
        assert line in combined, f"Line {i} is missing from reconstructed content"


def test_chunk_split_empty_content() -> None:
    """Test that empty content is handled correctly."""
    chunk = Chunk(category=ChunkCategory.callable, name="empty_func", line=1, content="")
    result = chunk.split()
    assert len(result) == 1, "Empty content should result in a single chunk"
    assert result[0] is chunk, "Should return the original chunk for empty content"


def test_chunk_split_exactly_at_max_size() -> None:
    """Test content that is exactly at the max_size limit."""
    exact_content = "x" * 1000
    chunk = Chunk(
        category=ChunkCategory.callable,
        name="exact_size_func",
        line=1,
        content=exact_content,
    )
    result = chunk.split(max_size=1000)
    assert len(result) == 1, "Content exactly at max_size should not be split"
    assert result[0] is chunk, "Should return the original chunk when exactly at max_size"
