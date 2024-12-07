from collections.abc import Generator
from pathlib import Path

import pytest

from mcpunk import db
from mcpunk.dependencies import deps
from mcpunk.settings import Settings


@pytest.fixture(scope="function", autouse=True)
def fresh_db(tmp_path: Path) -> Generator[None, None, None]:
    """Fiddle settings such that we have a fresh database"""
    settings = Settings(db_path=tmp_path / "test.db")
    assert not settings.db_path.absolute().exists()
    with deps.override(settings_partial=settings):
        db.init_db()
        yield


@pytest.fixture(scope="function", autouse=True)
def fiddle_settings() -> Generator[None, None, None]:
    """Fiddle misc settings for consistency in testing."""
    settings = Settings(
        include_chars_in_response=False,
    )
    with deps.override(settings_partial=settings):
        yield
