"""Shared pytest fixtures.

Every test runs fully offline with the mock AI provider, an isolated skills
directory, and a throwaway SQLite database.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch, tmp_path):
    """Point SkillForge at a temp skills dir + temp DB, force the mock provider."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "skillforge.db"

    monkeypatch.setenv("SKILLFORGE_AI_PROVIDER", "mock")
    monkeypatch.setenv("SKILLFORGE_SKILLS_DIR", str(skills_dir))
    monkeypatch.setenv("SKILLFORGE_DB_PATH", str(db_path))
    monkeypatch.setenv("SKILLFORGE_MODEL", "mock-model")

    # Reset cached singletons so the new env takes effect.
    from skillforge_api.settings import reload_settings
    from skillforge_api.database import reset_engine
    from skillforge_api.services.tool_catalog import get_catalog
    from skillforge_api.services import user_config

    reload_settings()
    reset_engine()
    get_catalog.cache_clear()
    # Isolate the user provider config to a temp file so tests never touch the
    # real ~/.skillforge/config.json.
    user_config.set_user_config_store(user_config.UserConfigStore(tmp_path / "config.json"))
    # Isolate the eval suite store to the same tmp area.
    from skillforge_api.services.eval import suites as eval_suites

    eval_suites.set_suite_store(eval_suites.EvalSuiteStore(tmp_path / "eval_suites"))
    # Isolate marketplace singletons (pairing tokens, approvals, stub adapter).
    from skillforge_api.services.marketplace import approvals, pairing
    from skillforge_api.services.marketplace.adapters import local_stub

    pairing.set_pairing_manager(pairing.PairingManager(tmp_path / "mp_tokens.json"))
    approvals.set_approval_manager(approvals.ApprovalManager(tmp_path / "mp_approvals.json"))
    local_stub.set_adapter(local_stub.LocalStubAdapter(tmp_path / "mp_stub"))

    yield

    reset_engine()
    get_catalog.cache_clear()
    user_config.set_user_config_store(None)
    eval_suites.set_suite_store(None)
    pairing.set_pairing_manager(None)
    approvals.set_approval_manager(None)
    local_stub.set_adapter(None)
