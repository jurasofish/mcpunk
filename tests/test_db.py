from pathlib import Path

import pytest
import sqlalchemy as sa

from mcpunk import db
from mcpunk.dependencies import deps
from mcpunk.settings import Settings


def test_init_db_creates_new_db(tmp_path: Path) -> None:
    # There's an auto-use fixture that uses tmp_path to set up a fresh db
    # for each test, and already runs init. So we need to just fiddle the path
    # to ensure we really do get a fresh db.
    tmp_path = tmp_path / "make_it_fresher" / "even_fresher"

    settings = Settings(db_path=tmp_path / "test.db")
    assert not settings.db_path.absolute().exists()
    with deps.override(settings=settings):
        db.init_db()
        assert settings.db_path.exists()

        # Verify PRAGMA statements
        expected_pragmas = [
            ("PRAGMA journal_mode", "wal"),
            ("PRAGMA synchronous", "1"),  # 1 is normal
            ("PRAGMA busy_timeout", "5000"),
            ("PRAGMA cache_size;", "-20000"),
            ("PRAGMA foreign_keys", "1"),
        ]
        with deps.session_maker().begin() as sess:
            for stmt, expected_result in expected_pragmas:
                result = sess.execute(sa.text(stmt)).scalar()
                assert str(result) == expected_result

            # Verify version
            version = sess.scalars(sa.select(db.DBVersion.version)).one()
            assert version == db.CURRENT_DB_VERSION

            actual_tables = sess.execute(
                sa.text("SELECT name FROM sqlite_master WHERE type='table';"),
            ).fetchall()
            actual_tables = sorted(actual_tables)
            expected_tables = sorted([("db_version",), ("task",)])
            assert actual_tables == expected_tables


def test_init_db_version_mismatch() -> None:
    db.init_db()  # This will double check the version is okay right now

    # Modify version to be different
    with deps.session_maker().begin() as sess:
        sess.execute(sa.delete(db.DBVersion))
        sess.add(db.DBVersion(version=db.CURRENT_DB_VERSION + "abcdefsg"))

    with pytest.raises(ValueError, match="Database version mismatch"):
        db.init_db()
