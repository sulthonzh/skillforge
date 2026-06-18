"""Tests for SQLite WAL + busy_timeout configuration (Tier 0.4).

These guard against regression of the "database is locked" error under
concurrency: the engine must enable WAL journal mode and a busy_timeout on
every connection.

DB isolation is provided by the global ``isolated_env`` autouse fixture in
conftest.py (sets SKILLFORGE_DB_PATH to a temp file + resets the engine), so
these tests don't define their own DB fixture.
"""

from __future__ import annotations

import threading
import time

from sqlalchemy import text

from skillforge_api.database import session_scope


def _pragma(session, name: str) -> str:
    """Read a PRAGMA value from a live session."""
    row = session.exec(text(f"PRAGMA {name}")).first()
    return str(row[0]) if row else ""


def test_wal_mode_enabled():
    """journal_mode must be WAL (was the default 'delete' rollback journal)."""
    with session_scope() as s:
        assert _pragma(s, "journal_mode").lower() == "wal"


def test_busy_timeout_set():
    """busy_timeout must be 5000ms (was 0 = fail immediately on lock)."""
    with session_scope() as s:
        assert _pragma(s, "busy_timeout") == "5000"


def test_synchronous_is_normal():
    """synchronous=NORMAL is safe with WAL and faster than FULL."""
    with session_scope() as s:
        # SQLite returns 1 for NORMAL (0=OFF, 1=NORMAL, 2=FULL, 3=EXTRA)
        assert _pragma(s, "synchronous") in ("1", "NORMAL")


def test_foreign_keys_enabled():
    with session_scope() as s:
        assert _pragma(s, "foreign_keys") == "1"


def test_pragmas_apply_to_every_connection():
    """PRAGMAs are set via a connect listener, so every pooled connection gets them."""
    # Open several distinct sessions (each gets its own connection from the pool).
    for _ in range(5):
        with session_scope() as s:
            assert _pragma(s, "journal_mode").lower() == "wal"
            assert _pragma(s, "busy_timeout") == "5000"


def test_concurrent_read_during_write():
    """A reader must not be blocked (or raise 'database is locked') while a writer holds the lock.

    This is the real-world scenario that caused 'database is locked' for users
    running an eval (many writes) while the Web UI polled the registry (reads).
    WAL lets the reader proceed; busy_timeout lets a would-be writer wait.
    """
    from skillforge_api.database import InstalledSkillRecord

    # Seed one row so the read has something to see.
    with session_scope() as s:
        s.add(
            InstalledSkillRecord(
                name="seed", title="Seed", domain="backend",
                version="0.1.0", path="/tmp/x",
            )
        )

    errors: list[Exception] = []
    barrier = threading.Barrier(2)

    def writer():
        try:
            barrier.wait(timeout=5)
            with session_scope() as s:
                for i in range(3):
                    s.add(
                        InstalledSkillRecord(
                            name=f"wal-write-{i}", title="WAL write test",
                            domain="backend", version="0.1.0", path="/tmp/x",
                        )
                    )
                    time.sleep(0.02)  # hold the write transaction briefly
        except Exception as exc:
            errors.append(exc)

    def reader():
        try:
            barrier.wait(timeout=5)
            with session_scope() as s:
                # Read concurrently with the writer.
                rows = s.exec(text("SELECT COUNT(*) FROM installed_skills")).first()
                assert rows[0] >= 1
        except Exception as exc:
            errors.append(exc)

    t1 = threading.Thread(target=writer)
    t2 = threading.Thread(target=reader)
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert errors == [], f"Concurrent read/write raised: {errors}"
