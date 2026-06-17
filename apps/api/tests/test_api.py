"""End-to-end API tests covering the main user flow."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from skillforge_api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_full_flow_plan_preview_validate_install(client):
    msg = "I need a backend skill for FastAPI, PostgreSQL, Docker, and Pytest"

    # 1) Plan.
    r = client.post("/api/chat/plan-skill", json={"message": msg})
    assert r.status_code == 200
    body = r.json()
    manifest = body["manifest"]
    assert manifest["skill"]["name"].startswith("backend-")
    assert body["explanation"]

    # 2) Preview.
    r2 = client.post("/api/skills/preview", json={"manifest": manifest})
    assert r2.status_code == 200
    paths = {f["path"] for f in r2.json()["files"]}
    assert {"SKILL.md", "README.md", "config.yaml"} <= paths

    # 3) Validate.
    r3 = client.post("/api/skills/validate", json={"manifest": manifest})
    assert r3.status_code == 200
    assert r3.json()["valid"] is True

    # 4) Install.
    r4 = client.post("/api/skills/install", json={"manifest": manifest, "overwrite": False})
    assert r4.status_code == 200
    assert r4.json()["installed"] is True

    # 5) List registry shows it.
    r5 = client.get("/api/registry/skills")
    names = [s["name"] for s in r5.json()["skills"]]
    assert manifest["skill"]["name"] in names


def test_install_conflict_returns_409(client):
    msg = "I need a backend skill for FastAPI, PostgreSQL, Docker, and Pytest"
    manifest = client.post("/api/chat/plan-skill", json={"message": msg}).json()["manifest"]
    # First install.
    client.post("/api/skills/install", json={"manifest": manifest, "overwrite": False})
    # Second without overwrite → 409.
    r = client.post("/api/skills/install", json={"manifest": manifest, "overwrite": False})
    assert r.status_code == 409


def test_plan_empty_message_returns_422(client):
    r = client.post("/api/chat/plan-skill", json={"message": ""})
    # Pydantic min_length=1 → 422.
    assert r.status_code == 422


def test_templates_endpoints(client):
    r = client.get("/api/templates/domains")
    assert r.status_code == 200
    assert len(r.json()["domains"]) >= 4

    r2 = client.get("/api/templates/catalog")
    assert r2.status_code == 200
    assert "domains" in r2.json()


def test_install_invalid_manifest_returns_400(client):
    manifest = client.post(
        "/api/chat/plan-skill",
        json={"message": "I need a backend skill for FastAPI, PostgreSQL, Docker, and Pytest"},
    ).json()["manifest"]
    # Make the name generic → invalid.
    manifest["skill"]["name"] = "backend"
    r = client.post("/api/skills/install", json={"manifest": manifest, "overwrite": False})
    assert r.status_code == 400
