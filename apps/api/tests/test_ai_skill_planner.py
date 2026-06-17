"""Tests for the AI skill planner (mock provider path)."""

from __future__ import annotations

import pytest

from skillforge_api.schemas.manifest import GENERIC_NAMES
from skillforge_api.services.ai_skill_planner import (
    AISkillPlanner,
    _sanitize_skill_name,
    _slugify_domain,
    _slugify_tool,
)


def test_plan_returns_manifest_and_explanation():
    planner = AISkillPlanner()
    manifest, explanation = planner.plan(
        "I need a backend skill for FastAPI, PostgreSQL, Docker, and Pytest"
    )
    assert manifest.skill.domain == "Backend Engineering"
    assert isinstance(explanation, str) and len(explanation) > 0


def test_plan_skill_name_is_specific_and_kebab():
    planner = AISkillPlanner()
    manifest, _ = planner.plan(
        "I need a backend skill for FastAPI, PostgreSQL, Docker, and Pytest"
    )
    name = manifest.skill.name
    assert name not in GENERIC_NAMES, f"{name} is generic"
    assert name.startswith("backend-")
    assert "-" in name
    # Name reflects the primary tools.
    assert "fastapi" in name


@pytest.mark.parametrize(
    "message,expected_domain",
    [
        ("data engineering with Airflow, dbt, and BigQuery", "Data Engineering"),
        ("devops with Kubernetes, Helm, and Terraform", "DevOps"),
        ("AI RAG skill with LangChain and pgvector", "AI Engineering"),
        ("observability with OpenTelemetry and Grafana", "Observability"),
    ],
)
def test_plan_classifies_domains(message, expected_domain):
    manifest, _ = AISkillPlanner().plan(message)
    assert manifest.skill.domain == expected_domain


def test_plan_includes_at_least_two_tools():
    manifest, _ = AISkillPlanner().plan("backend skill for FastAPI and PostgreSQL")
    assert len([t for t in manifest.tools if t.enabled]) >= 2


def test_plan_mentions_detected_tools_come_first():
    manifest, _ = AISkillPlanner().plan(
        "I need a backend skill for FastAPI, PostgreSQL, Docker, and Pytest"
    )
    names = [t.name for t in manifest.tools]
    # Explicitly requested tools should appear before fill-ins.
    for required in ("FastAPI", "PostgreSQL", "Docker", "Pytest"):
        assert required in names


def test_plan_workflow_non_empty():
    manifest, _ = AISkillPlanner().plan("backend skill for FastAPI")
    assert len(manifest.workflow) >= 3


def test_plan_stamps_ai_provenance():
    manifest, _ = AISkillPlanner().plan("backend skill for FastAPI and PostgreSQL")
    assert manifest.ai.generated_by == "skillforge"
    assert manifest.ai.planner_model
    assert manifest.ai.created_at is not None


def test_plan_rejects_empty_message():
    with pytest.raises(ValueError):
        AISkillPlanner().plan("")


def test_sanitize_skill_name_helpers():
    assert _sanitize_skill_name("FastAPI Postgres!") == "fastapi-postgres"
    assert _slugify_tool("OpenAI-compatible API") == "openai"
    assert _slugify_domain("data_engineering") == "data"


def test_plan_data_skill_name_reflects_tools():
    manifest, _ = AISkillPlanner().plan("data engineering with Airflow, dbt, and BigQuery")
    name = manifest.skill.name
    assert name.startswith("data-")
    # Primary orchestration + transformation tools appear in the name.
    assert "airflow" in name
    assert "dbt" in name
