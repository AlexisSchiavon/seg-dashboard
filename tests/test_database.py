from sqlalchemy import text

from app.database import engine


def test_sqlite_pragmas():
    with engine.connect() as conn:
        journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar()
        busy_timeout = conn.execute(text("PRAGMA busy_timeout")).scalar()

    assert journal_mode == "wal"
    assert busy_timeout == 10000
