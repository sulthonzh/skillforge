"""SQLite + SQLModel database setup.

A tiny registry table records every skill that SkillForge installs locally.
The generator and installer never need the DB — they operate on the
filesystem — but the registry persists metadata so the Web UI and CLI can
list, inspect, and remove installed skills quickly.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from sqlmodel import Field, Session, SQLModel, create_engine, select

from .settings import get_settings


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
        SQLModel.metadata.create_all(_engine)
    return _engine


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
