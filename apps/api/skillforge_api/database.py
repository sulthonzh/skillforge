"""SQLite + SQLModel database setup.

A tiny registry table records every skill that SkillForge installs locally.
The generator and installer never need the DB — they operate on the
filesystem — but the registry persists metadata so the Web UI and CLI can
list, inspect, and remove installed skills quickly.

Concurrency: SQLite is configured for WAL journal mode with a 5s busy_timeout
on every connection (see ``_set_sqlite_pragmas``). WAL allows concurrent
readers alongside a single writer, and ``busy_timeout`` makes a blocked writer
wait instead of immediately raising ``OperationalError: database is locked``.
This matters because the eval runner opens many short write transactions per
run on the same event-loop thread as everything else.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import event
from sqlmodel import Field, Session, SQLModel, create_engine

from .settings import get_settings

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InstalledSkillRecord(SQLModel, table=True):
    """One row per locally installed skill."""

    __tablename__ = "installed_skills"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    title: str = Field(default="")
    domain: str = Field(default="")
    version: str = Field(default="0.1.0")
    path: str = Field(default="")
    installed_at: datetime = Field(default_factory=_utcnow)


class EvalSuiteRecord(SQLModel, table=True):
    """A named, editable set of test prompts (also mirrored to JSON on disk)."""

    __tablename__ = "eval_suites"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: str = Field(default="")
    # JSON-encoded list of prompt strings.
    prompts_json: str = Field(default="[]")
    created_at: datetime = Field(default_factory=_utcnow)


class EvalRunRecord(SQLModel, table=True):
    """One batch eval run of a skill against a suite."""

    __tablename__ = "eval_runs"

    id: int | None = Field(default=None, primary_key=True)
    suite_id: int | None = Field(default=None, index=True, foreign_key="eval_suites.id")
    suite_name: str = Field(default="", index=True)
    skill_name: str = Field(index=True)
    skill_version: str = Field(default="")
    provider: str = Field(default="")
    model: str = Field(default="")
    aggregate_score: float | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow)


class EvalResultRecord(SQLModel, table=True):
    """One (run, prompt) scored result."""

    __tablename__ = "eval_results"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(index=True, foreign_key="eval_runs.id")
    prompt: str = Field(default="")
    response: str = Field(default="")
    score: float | None = Field(default=None)
    reasoning: str = Field(default="")
    status: str = Field(default="ok")  # ok | error | skipped
    created_at: datetime = Field(default_factory=_utcnow)



_engine = None


def get_engine():
    """Lazily create the SQLite engine and create tables on first use."""
    global _engine
    if _engine is None:
        settings = get_settings()
        # Ensure the parent directory of the SQLite file exists.
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            settings.db_url,
            echo=False,
            connect_args={"check_same_thread": False},
        )
        # Set connection-level PRAGMAs on every new DBAPI connection. WAL mode
        # allows concurrent readers + one writer (avoids "database is locked"
        # under the eval runner's many short transactions); busy_timeout makes
        # a blocked writer wait 5s instead of failing immediately;
        # synchronous=NORMAL is safe with WAL and faster than FULL.
        event.listens_for(_engine, "connect")(_set_sqlite_pragmas)
        SQLModel.metadata.create_all(_engine)
    return _engine


def _set_sqlite_pragmas(dbapi_conn, _connection_record) -> None:
    """Apply WAL + busy_timeout to each raw SQLite connection.

    Registered as a SQLAlchemy ``connect`` listener so the PRAGMAs apply even
    to connections opened by the pool after the engine is created.
    """
    cur = dbapi_conn.cursor()
    try:
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA foreign_keys=ON")
    finally:
        cur.close()


def reset_engine() -> None:
    """Drop the cached engine (used by tests that switch DB paths)."""
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager that yields a session and commits on success."""
    engine = get_engine()
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
