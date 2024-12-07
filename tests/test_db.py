from pathlib import Path

import sqlalchemy as sa

from mcpunk import db
from mcpunk.dependencies import deps
from mcpunk.settings import Settings


def test_init_db_creates_new_db(tmp_path: Path) -> None:
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
