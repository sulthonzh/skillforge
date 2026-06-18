"""Tests for the skill installer."""

from __future__ import annotations

import pytest

from skillforge_api.services.ai_skill_planner import AISkillPlanner
from skillforge_api.services.skill_installer import InstallerError, SkillInstaller
from skillforge_api.services.skill_registry import SkillRegistry
from skillforge_api.settings import get_settings


def _plan():
    return AISkillPlanner().plan(
        "I need a backend skill for FastAPI, PostgreSQL, Docker, and Pytest"
    )[0]


def test_install_writes_files_and_registers():
    manifest = _plan()
    installer = SkillInstaller()
    outcome = installer.install(manifest)
    assert outcome.installed is True
    # All required files exist on disk.
    root = get_settings().skills_dir / manifest.skill.name
    for fname in ("SKILL.md", "README.md", "config.yaml"):
        assert (root / fname).is_file(), f"{fname} missing"
    # Registry has the skill.
    skills = SkillRegistry().list_installed()
    assert any(s.name == manifest.skill.name for s in skills)


def test_install_refuses_overwrite_without_flag():
    manifest = _plan()
    installer = SkillInstaller()
    installer.install(manifest)
    second = installer.install(manifest, overwrite=False)
    assert second.installed is False
    assert second.skipped_existing is True


def test_install_overwrites_with_flag():
    manifest = _plan()
    installer = SkillInstaller()
    installer.install(manifest)
    second = installer.install(manifest, overwrite=True)
    assert second.installed is True


def test_install_rejects_invalid_manifest():
    manifest = _plan()
    manifest.skill.name = "backend"  # generic → invalid
    installer = SkillInstaller()
    with pytest.raises(InstallerError):
        installer.install(manifest)


def test_remove_deletes_files_and_registry():
    manifest = _plan()
    installer = SkillInstaller()
    installer.install(manifest)
    assert installer.remove(manifest.skill.name) is True
    root = get_settings().skills_dir / manifest.skill.name
    assert not root.exists()
    assert SkillRegistry().get(manifest.skill.name) is None


def test_remove_nonexistent_returns_false():
    assert SkillInstaller().remove("does-not-exist") is False


# ---------------------------------------------------------------------------
# Atomic install (Tier 0.3) — a mid-write failure must not delete the old skill.
# ---------------------------------------------------------------------------


def test_install_overwrite_failure_preserves_old_skill(monkeypatch):
    """If writing the new files fails, the previously-installed skill survives.

    Regression for the old non-atomic path: ``shutil.rmtree(target)`` ran
    BEFORE ``_write_files``, so a failure mid-write left the user with no skill
    where there was one. The atomic path stages to a temp dir + os.replace, so
    the old skill is untouched until the new one is fully written.
    """
    from skillforge_api.services import skill_installer as mod

    manifest = _plan()
    installer = SkillInstaller()

    # Install once so there's an existing skill on disk.
    installer.install(manifest)
    target = get_settings().skills_dir / manifest.skill.name
    old_skill_md = (target / "SKILL.md").read_text()
    assert old_skill_md  # sanity

    # Sabotage _write_files to fail partway through. It's called against the
    # STAGING dir (not the live target), so the live target must survive.
    real_write = mod._write_files
    call_count = {"n": 0}

    def failing_write(root, files):
        call_count["n"] += 1
        # Let it create the staging dir + write one file, then blow up.
        real_write(root, files[:1])
        raise OSError("simulated disk full mid-write")

    monkeypatch.setattr(mod, "_write_files", failing_write)

    with pytest.raises(OSError, match="simulated disk full"):
        installer.install(manifest, overwrite=True)

    # The old skill must still be on disk, intact — that's the whole point.
    assert target.exists(), "old skill dir was deleted by a failed overwrite"
    assert (target / "SKILL.md").read_text() == old_skill_md
    # No staging leftovers.
    leftovers = [p for p in target.parent.iterdir() if p.name.startswith(f".{manifest.skill.name}.staging")]
    assert leftovers == [], f"staging dir left behind: {leftovers}"


def test_install_atomic_leaves_no_staging_on_success():
    """After a successful install, no staging or backup dirs remain."""
    manifest = _plan()
    installer = SkillInstaller()
    installer.install(manifest)
    skills_dir = get_settings().skills_dir
    leftovers = [
        p
        for p in skills_dir.iterdir()
        if p.name.startswith(f".{manifest.skill.name}.")
        and ("staging" in p.name or "backup" in p.name)
    ]
    assert leftovers == [], f"temp dirs left behind after successful install: {leftovers}"


def test_install_atomic_overwrite_replaces_old_content():
    """Overwriting actually swaps in new content (not just survives failure)."""
    manifest = _plan()
    installer = SkillInstaller()
    installer.install(manifest)
    target = get_settings().skills_dir / manifest.skill.name
    before = (target / "SKILL.md").read_text()

    # Mutate the manifest so the generated content differs.
    manifest = manifest.model_copy(
        update={"skill": manifest.skill.model_copy(update={"title": "Completely New Title"})}
    )
    installer.install(manifest, overwrite=True)

    after = (target / "SKILL.md").read_text()
    assert after != before, "overwrite did not replace content"
    assert "Completely New Title" in after


def test_remove_deletes_db_before_fs(monkeypatch):
    """remove() must delete the registry row BEFORE rmtree, so a DB failure
    leaves the skill files recoverable on disk rather than a dangling row."""
    manifest = _plan()
    installer = SkillInstaller()
    installer.install(manifest)
    target = get_settings().skills_dir / manifest.skill.name
    assert target.exists()

    # Track call order: patch the installer's repository.delete and shutil.rmtree.
    order: list[str] = []

    def failing_delete(name):
        order.append("db_delete")
        raise RuntimeError("simulated DB outage")

    import shutil

    real_rmtree = shutil.rmtree

    def tracking_rmtree(path, *a, **kw):
        order.append("rmtree")
        return real_rmtree(path, *a, **kw)

    monkeypatch.setattr(installer._repository, "delete", failing_delete)
    monkeypatch.setattr(shutil, "rmtree", tracking_rmtree)

    # remove() should raise (the DB error propagates) — but rmtree must NOT
    # have run, so the skill files survive.
    with pytest.raises(RuntimeError, match="simulated DB outage"):
        installer.remove(manifest.skill.name)

    assert order == ["db_delete"], f"rmtree ran before db_delete: {order}"
    assert target.exists(), "skill files were deleted despite the DB failure"
    assert (target / "SKILL.md").is_file()


def test_compute_bump_raises_on_malformed_yaml():
    """Malformed existing config.yaml must raise, not silently skip the bump."""
    manifest = _plan()
    installer = SkillInstaller()
    installer.install(manifest)
    target = get_settings().skills_dir / manifest.skill.name

    # Corrupt the config.yaml.
    (target / "config.yaml").write_text("this: is: not: valid: yaml: [")

    with pytest.raises(InstallerError, match="malformed YAML"):
        installer._compute_bump(manifest, target)
