"""Registry repository.

Thin SQLModel-backed CRUD over the ``installed_skills`` table. The filesystem
is the source of truth for installed skill contents; this table is a fast index
the UI and CLI read when listing skills.
"""

from __future__ import annotations

from sqlmodel import select

from ..database import InstalledSkillRecord, session_scope


class RegistryRepository:
    """CRUD over installed-skill records."""

    def list_all(self) -> list[InstalledSkillRecord]:
        with session_scope() as session:
            rows = session.exec(select(InstalledSkillRecord).order_by(InstalledSkillRecord.name)).all()
            # Detach from session.
            return [InstalledSkillRecord(**r.model_dump()) for r in rows]

    def get(self, name: str) -> InstalledSkillRecord | None:
        with session_scope() as session:
            row = session.exec(
                select(InstalledSkillRecord).where(InstalledSkillRecord.name == name)
            ).first()
            return InstalledSkillRecord(**row.model_dump()) if row else None

    def exists(self, name: str) -> bool:
        return self.get(name) is not None

    def upsert(self, **fields) -> InstalledSkillRecord:
        name = fields["name"]
        with session_scope() as session:
            existing = session.exec(
                select(InstalledSkillRecord).where(InstalledSkillRecord.name == name)
            ).first()
            if existing:
                for key, value in fields.items():
                    setattr(existing, key, value)
                session.add(existing)
                session.flush()
                return InstalledSkillRecord(**existing.model_dump())
            row = InstalledSkillRecord(**fields)
            session.add(row)
            session.flush()
            return InstalledSkillRecord(**row.model_dump())

    def delete(self, name: str) -> bool:
        with session_scope() as session:
            row = session.exec(
                select(InstalledSkillRecord).where(InstalledSkillRecord.name == name)
            ).first()
            if not row:
                return False
            session.delete(row)
            return True
