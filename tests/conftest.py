import hashlib
from collections.abc import Generator
from pathlib import Path

import pytest

from mcpunk.dependencies import deps
from mcpunk.settings import Settings


@pytest.fixture(scope="function", autouse=True)
def fiddle_settings() -> Generator[None, None, None]:
    """Fiddle misc settings for consistency in testing."""
    settings = Settings(
        include_chars_in_response=False,
        file_watch_refresh_freq_seconds=0.0,
    )
    with deps.override(settings_partial=settings):
        yield


@pytest.fixture
def test_id(request: pytest.FixtureRequest) -> str:
    """A (probably) unique ID for each test"""
    test_hash = hashlib.md5(request.node.nodeid.encode()).hexdigest()  # noqa: S324
    assert len(test_hash) == 32
    return f"{request.node.name[: (60 - len(test_hash) - 1)]}_{test_hash}"


class FileSet:
    def __init__(self, root: Path) -> None:
        self.root = root

    def add_file(self, fname: str, src: str) -> None:
        new_path = self.root / fname
        new_path.parent.mkdir(parents=True, exist_ok=True)
        new_path.write_text(src)


@pytest.fixture
def basic_file_set(tmp_path_factory: pytest.TempPathFactory) -> FileSet:
    """A basic file set with two files."""
    tmp_path = tmp_path_factory.mktemp("test")
    fs = FileSet(tmp_path)
    fs.add_file("a.py", "a=1")
    fs.add_file("b.py", "b=2\ndef f(a: int=1):\n    return a")
    return fs
