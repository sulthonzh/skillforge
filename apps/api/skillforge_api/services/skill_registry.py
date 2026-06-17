"""Skill registry service.

A thin facade over :class:`RegistryRepository` and :class:`SkillInstaller` that
the API and CLI use to list, inspect, validate, and remove installed skills.
Keeping it separate from the repository means the Web UI's "list installed
skills" view doesn't need to know SQLModel details.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..repositories.registry_repository import RegistryRepository
from ..schemas.registry import InstalledSkill
from ..settings import Settings, get_settings
from .skill_installer import SkillInstaller
from .skill_validator import SkillValidator, ValidationResult


@dataclass
class RegistryEntry:
    name: str
    title: str
    domain: str
    path: str
    version: str
    installed_at: str | None = None


class SkillRegistry:
    """Read + mutate installed skills."""

    def __init__(
        self,
        repository: RegistryRepository | None = None,
        installer: SkillInstaller | None = None,
        validator: SkillValidator | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._repo = repository or RegistryRepository()
        self._installer = installer or SkillInstaller(repository=self._repo)
        self._validator = validator or SkillValidator()
        self._settings = settings or get_settings()

    def list_installed(self) -> list[InstalledSkill]:
        rows = self._repo.list_all()
        return [
            InstalledSkill(
                name=r.name,
                title=r.title,
                domain=r.domain,
                path=r.path,
                version=r.version,
                installed_at=r.installed_at,
            )
            for r in rows
        ]

    def get(self, name: str) -> InstalledSkill | None:
        row = self._repo.get(name)
        if not row:
            return None
        return InstalledSkill(
            name=row.name,
            title=row.title,
            domain=row.domain,
            path=row.path,
            version=row.version,
            installed_at=row.installed_at,
        )

    def validate_installed(self, name: str) -> ValidationResult:
        row = self._repo.get(name)
        if not row:
            result = ValidationResult()
            result.add("not_installed", f"No installed skill named {name!r}.")
            return result
        return self._validator.validate_directory(row.path)

    def remove(self, name: str) -> bool:
        return self._installer.remove(name)
