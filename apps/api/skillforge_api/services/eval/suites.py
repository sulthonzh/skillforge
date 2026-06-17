"""Eval suites — named, editable sets of test prompts.

Suites are stored both in SQLite (for fast listing) and as JSON files at
``~/.skillforge/eval_suites/<name>.json`` (so they're easy to edit/share, like
skills). A default "General" suite is seeded on first run.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from ...database import EvalSuiteRecord, session_scope
from ...settings import get_settings


class SuiteNotFound(KeyError):
    """Raised when a named suite doesn't exist."""


# A broad, cross-domain default suite. Good for apples-to-apples comparisons
# between skills of different domains; each skill is also run against its own
# example_prompts by default.
DEFAULT_SUITE = {
    "name": "General",
    "description": "General engineering prompts for cross-skill comparison.",
    "prompts": [
        "Design a clean module structure for a new service in this domain.",
        "What are the three biggest risks in this stack, and how would you mitigate them?",
        "Write a concise production-readiness checklist for a project using these tools.",
        "Explain the key architectural decisions and trade-offs you'd make here.",
        "Outline a testing strategy appropriate for this skill's workflow.",
    ],
}


class EvalSuiteStore:
    """CRUD over eval suites (SQLite + JSON mirror)."""

    def __init__(self, root_dir: str | Path | None = None) -> None:
        if root_dir is not None:
            self._root = Path(root_dir)
        else:
            self._root = get_settings().skills_dir.parent / "eval_suites"
        self._lock = RLock()

    @property
    def root(self) -> Path:
        return self._root

    # ---- seed ----
    def seed_default(self) -> None:
        """Create the default suite if no suites exist yet. Idempotent."""
        with self._lock:
            with session_scope() as session:
                from sqlmodel import select

                existing = session.exec(select(EvalSuiteRecord)).first()
                if existing is not None:
                    return
            self.create(DEFAULT_SUITE["name"], DEFAULT_SUITE["description"], DEFAULT_SUITE["prompts"])

    # ---- read ----
    def list_all(self) -> list[dict[str, Any]]:
        with session_scope() as session:
            from sqlmodel import select

            rows = session.exec(select(EvalSuiteRecord).order_by(EvalSuiteRecord.name)).all()
            return [self._row_to_dict(r) for r in rows]

    def get(self, name: str) -> dict[str, Any]:
        with session_scope() as session:
            from sqlmodel import select

            row = session.exec(
                select(EvalSuiteRecord).where(EvalSuiteRecord.name == name)
            ).first()
            if not row:
                raise SuiteNotFound(name)
            return self._row_to_dict(row)

    def _row_to_dict(self, row: EvalSuiteRecord) -> dict[str, Any]:
        try:
            prompts = json.loads(row.prompts_json) if row.prompts_json else []
        except json.JSONDecodeError:
            prompts = []
        return {
            "id": row.id,
            "name": row.name,
            "description": row.description,
            "prompts": prompts,
            "created_at": row.created_at,
        }

    # ---- write ----
    def create(self, name: str, description: str, prompts: list[str]) -> dict[str, Any]:
        name = (name or "").strip()
        if not name:
            raise ValueError("Suite name is required")
        prompts = [p.strip() for p in prompts if p and p.strip()]
        with self._lock:
            with session_scope() as session:
                from sqlmodel import select

                existing = session.exec(
                    select(EvalSuiteRecord).where(EvalSuiteRecord.name == name)
                ).first()
                if existing:
                    existing.description = description
                    existing.prompts_json = json.dumps(prompts)
                    session.add(existing)
                    row = existing
                else:
                    row = EvalSuiteRecord(
                        name=name,
                        description=description,
                        prompts_json=json.dumps(prompts),
                    )
                    session.add(row)
                    session.flush()
            # Mirror to JSON for easy sharing.
            self._write_json(name, description, prompts)
            return self.get(name)

    def delete(self, name: str) -> bool:
        with self._lock:
            with session_scope() as session:
                from sqlmodel import select

                row = session.exec(
                    select(EvalSuiteRecord).where(EvalSuiteRecord.name == name)
                ).first()
                if not row:
                    return False
                session.delete(row)
            (self._root / f"{name}.json").unlink(missing_ok=True)
            return True

    def _write_json(self, name: str, description: str, prompts: list[str]) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        path = self._root / f"{name}.json"
        path.write_text(
            json.dumps(
                {
                    "name": name,
                    "description": description,
                    "prompts": prompts,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )


# ---- process-wide singleton ----
_store: EvalSuiteStore | None = None


def get_suite_store() -> EvalSuiteStore:
    global _store
    if _store is None:
        _store = EvalSuiteStore()
    return _store


def set_suite_store(store: EvalSuiteStore | None) -> None:
    """Override the singleton (tests pass a temp-dir store)."""
    global _store
    _store = store
