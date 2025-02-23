import logging
from pathlib import Path
from string import ascii_lowercase

import pytest

from mcpunk.util import create_file_tree, log_inputs_outputs, matches_filter, rand_str


@pytest.mark.parametrize("log_level", (logging.DEBUG, logging.INFO, "WARNING"))
def test_log_inputs(
    caplog: pytest.LogCaptureFixture,
    log_level: int | str,
) -> None:
    """Test log_inputs decorator captures function inputs and outputs."""
    caplog.set_level(logging.DEBUG)

    @log_inputs_outputs(log_level=log_level)
    def example_func(a: int, *, b: str = "test") -> str:
        return f"{a}{b}"

    result = example_func(1, b="value")
    assert result == "1value"

    expect_log_to_contain_snippets = [
        "Calling tool example_func with inputs:",
        "Arg_0=1",
        "b='value'",
        "resp='1value'",
    ]
    for t in expect_log_to_contain_snippets:
        assert t in caplog.text, t
        for record in caplog.records:
            if t in record.message:
                assert log_level in (record.levelno, record.levelname), record.levelno

    assert "Calling tool example_func with inputs:" in caplog.text
    assert "Arg_0=1" in caplog.text
    assert "b='value'" in caplog.text
    assert "resp='1value'" in caplog.text


def test_create_file_tree(tmp_path: Path) -> None:
    """Test create_file_tree generates correct compact text output."""
    # Set up test files
    (tmp_path / "dir1").mkdir()
    (tmp_path / "dir1/file1.txt").touch()
    (tmp_path / "dir1/other.txt").touch()
    (tmp_path / "dir1/subdir").mkdir()
    (tmp_path / "dir1/subdir/file2.txt").touch()
    (tmp_path / "file3.txt").touch()
    (tmp_path / "dir2/dir4/dir5").mkdir(parents=True)
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs/app.log").touch()
    (tmp_path / "logs/error.log").touch()

    paths = {
        tmp_path / "dir1",
        tmp_path / "dir1/file1.txt",
        tmp_path / "dir1/other.txt",
        tmp_path / "dir1/subdir",
        tmp_path / "dir1/subdir/file2.txt",
        tmp_path / "file3.txt",
        tmp_path / "dir2/dir4/dir5",
        tmp_path / "logs",
        tmp_path / "logs/app.log",
        tmp_path / "logs/error.log",
    }

    result = create_file_tree(
        project_root=tmp_path,
        paths=paths,
    )

    expected = (
        ".: file3.txt\ndir1: file1.txt; other.txt\ndir1/subdir: file2.txt\n"
        "logs: app.log; error.log\n"
    )
    assert result == expected


def test_create_file_tree_with_filter(tmp_path: Path) -> None:
    """Test create_file_tree with filter parameter."""
    (tmp_path / "test.py").touch()
    (tmp_path / "main.py").touch()
    (tmp_path / "data.txt").touch()

    paths = {
        tmp_path / "test.py",
        tmp_path / "main.py",
        tmp_path / "data.txt",
    }

    result = create_file_tree(
        project_root=tmp_path,
        paths=paths,
        filter_=[".py"],
    )
    assert result == ".: main.py; test.py\n"


def test_create_file_tree_depth_limit(tmp_path: Path) -> None:
    """Test create_file_tree with depth limit."""
    (tmp_path / "file0.txt").touch()
    (tmp_path / "dir1/dir2/dir3").mkdir(parents=True)
    (tmp_path / "dir1/file1.txt").touch()
    (tmp_path / "dir1/dir2/file2.txt").touch()
    (tmp_path / "dir1/dir2/dir3/file3.txt").touch()

    paths = {
        tmp_path / p
        for p in [
            "file0.txt",
            "dir1",
            "dir1/file1.txt",
            "dir1/dir2",
            "dir1/dir2/file2.txt",
            "dir1/dir2/dir3",
            "dir1/dir2/dir3/file3.txt",
        ]
    }

    result = create_file_tree(
        project_root=tmp_path,
        paths=paths,
        limit_depth_from_root=2,
    )
    assert result == ".: file0.txt\ndir1: file1.txt\n"


def test_rand_str() -> None:
    """Test rand_str generates strings correctly."""
    # Test default length
    result = rand_str()
    assert len(result) == 10
    assert all(c in ascii_lowercase for c in result)

    # Test custom length
    result = rand_str(n=5)
    assert len(result) == 5

    # Test custom characters
    result = rand_str(chars="ABC")
    assert len(result) == 10
    assert all(c in "ABC" for c in result)


def test_matches_filter() -> None:
    """Test matches_filter with different filter types."""
    # Test None filter
    assert matches_filter(None, "test") is True
    assert matches_filter(None, None) is True

    # Test list filter
    assert matches_filter(["abc", "def"], "abcdef") is True
    assert matches_filter(["xyz", "123"], "abcdef") is False
    assert matches_filter(["abc"], None) is False
