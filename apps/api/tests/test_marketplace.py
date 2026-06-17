"""Tests for the marketplace: pairing, packaging, stub adapter, bridge auth, approvals."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from skillforge_api.main import create_app
from skillforge_api.services.bootstrap import bootstrap_skill_creator
from skillforge_api.services.marketplace.adapters import LocalStubAdapter, set_adapter
from skillforge_api.services.marketplace.approvals import (
    ApprovalManager,
    ApprovalStatus,
    set_approval_manager,
)
from skillforge_api.services.marketplace.pairing import (
    PairingManager,
    set_pairing_manager,
)
from skillforge_api.services.marketplace.packaging import SkillPackager


@pytest.fixture
def client():
    return TestClient(create_app())


def _ensure_skill():
    bootstrap_skill_creator()


# ---- PairingManager ----


def test_pairing_code_generated_and_single_use():
    mgr = PairingManager()
    code = mgr.generate_code()
    assert len(code) == 6
    result = mgr.complete_pairing(code)
    assert result is not None
    plaintext, info = result
    assert len(plaintext) > 20
    assert "registry:read" in info.scopes
    # Single-use: second attempt fails.
    assert mgr.complete_pairing(code) is None


def test_pairing_invalid_code_returns_none():
    assert PairingManager().complete_pairing("BOGUS0") is None


def test_token_validate_and_revoke():
    mgr = PairingManager()
    code = mgr.generate_code()
    plaintext, info = mgr.complete_pairing(code)
    # Valid token.
    assert mgr.validate(plaintext) is not None
    assert mgr.has_scope(plaintext, "skills:install") is True
    # Revoke.
    assert mgr.revoke(info.id) is True
    assert mgr.validate(plaintext) is None
    assert mgr.has_scope(plaintext, "registry:read") is False


def test_token_wrong_secret_fails():
    mgr = PairingManager()
    mgr.generate_code()
    assert mgr.validate("not-a-real-token") is None


# ---- SkillPackager ----


def test_packaging_round_trip():
    _ensure_skill()
    packager = SkillPackager()
    pkg_bytes = packager.pack("skill-creator")
    assert len(pkg_bytes) > 100
    manifest, files = packager.unpack(pkg_bytes)
    assert manifest.skill.name == "skill-creator"
    # All key files present.
    assert "SKILL.md" in files
    assert "README.md" in files
    assert "config.yaml" in files


def test_packaging_unknown_skill_raises():
    with pytest.raises(Exception):
        SkillPackager().pack("does-not-exist")


# ---- LocalStubAdapter ----


def test_stub_publish_search_download():
    _ensure_skill()
    adapter = LocalStubAdapter()
    pkg = SkillPackager().pack("skill-creator")
    listing = adapter.publish(
        skill_name="skill-creator",
        package_bytes=pkg,
        listing_meta={"title": "Skill Creator", "description": "meta skill", "author": "tester"},
    )
    assert listing.name == "skill-creator"
    # Search finds it.
    results = adapter.search("skill")
    assert any(r.name == "skill-creator" for r in results)
    # Get.
    assert adapter.get(listing.id) is not None
    # Download returns the bundle.
    downloaded = adapter.download(listing.id)
    assert downloaded == pkg


def test_stub_search_empty():
    assert LocalStubAdapter().search("nothing") == []


def test_stub_delete():
    _ensure_skill()
    adapter = LocalStubAdapter()
    pkg = SkillPackager().pack("skill-creator")
    listing = adapter.publish(skill_name="skill-creator", package_bytes=pkg, listing_meta={})
    assert adapter.delete(listing.id) is True
    assert adapter.get(listing.id) is None
    assert adapter.delete(listing.id) is False


# ---- ApprovalManager ----


def test_approval_lifecycle():
    mgr = ApprovalManager()
    approval = mgr.create("test-skill", '{"test": true}', source="marketplace:x")
    assert approval.status == "pending"
    assert len(mgr.list_pending()) == 1
    # Approve.
    approved = mgr.set_status(approval.id, ApprovalStatus.APPROVED)
    assert approved.status == "approved"
    assert mgr.list_pending() == []
    # Reject path.
    a2 = mgr.create("other", "{}")
    assert mgr.set_status(a2.id, ApprovalStatus.REJECTED).status == "rejected"


# ---- Bridge router (auth + scope) ----


def _pair(client):
    """Helper: generate a code and complete pairing → returns a token."""
    code = client.post("/api/marketplace/pair/code").json()["code"]
    r = client.post("/api/bridge/pair/complete", json={"code": code})
    assert r.status_code == 200
    return r.json()["token"]


def test_bridge_whoami_requires_token(client):
    r = client.get("/api/bridge/whoami")
    assert r.status_code == 401


def test_bridge_whoami_with_valid_token(client):
    token = _pair(client)
    r = client.get("/api/bridge/whoami", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert "scopes" in r.json()


def test_bridge_revoked_token_rejected(client):
    token = _pair(client)
    tokens = client.get("/api/marketplace/tokens").json()["tokens"]
    token_id = tokens[0]["id"]
    client.delete(f"/api/marketplace/tokens/{token_id}")
    r = client.get("/api/bridge/whoami", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_bridge_list_skills_requires_scope(client):
    token = _pair(client)
    r = client.get("/api/bridge/skills", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert "skills" in data


def test_bridge_publish(client):
    _ensure_skill()
    token = _pair(client)
    r = client.post(
        "/api/bridge/skills/publish",
        json={"skill_name": "skill-creator"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["published"] is True


def test_bridge_install_creates_approval(client):
    token = _pair(client)
    # Use a minimal valid manifest.
    from skillforge_api.services.ai_skill_planner import AISkillPlanner

    manifest, _ = AISkillPlanner().plan("backend skill for FastAPI and PostgreSQL")
    r = client.post(
        "/api/bridge/skills/install",
        json={"manifest": manifest.model_dump(mode="json")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert r.json()["installed"] is False
    assert "pending_approval" in r.json()


# ---- Marketplace router (local UI, no token) ----


def test_marketplace_search_empty(client):
    r = client.get("/api/marketplace/search")
    assert r.status_code == 200
    assert r.json()["count"] == 0


def test_marketplace_publish_then_search(client):
    _ensure_skill()
    r = client.post(
        "/api/marketplace/publish",
        json={"skill_name": "skill-creator", "title": "Skill Creator", "description": "meta"},
    )
    assert r.status_code == 200
    listing_id = r.json()["listing"]["id"]
    # Search finds it.
    results = client.get("/api/marketplace/search?q=skill").json()["results"]
    assert any(l["id"] == listing_id for l in results)


def test_marketplace_install_from_market_creates_approval(client):
    _ensure_skill()
    # Publish first.
    pub = client.post("/api/marketplace/publish", json={"skill_name": "skill-creator"}).json()
    listing_id = pub["listing"]["id"]
    # Install from marketplace.
    r = client.post("/api/marketplace/install", json={"listing_id": listing_id})
    assert r.status_code == 200
    assert r.json()["installed"] is False
    approval_id = r.json()["pending_approval"]
    # Approve.
    r2 = client.post(f"/api/marketplace/pending/{approval_id}/approve", json={"overwrite": True})
    assert r2.status_code == 200
    assert r2.json()["installed"] is True


def test_marketplace_pair_code(client):
    r = client.post("/api/marketplace/pair/code")
    assert r.status_code == 200
    assert len(r.json()["code"]) == 6


def test_marketplace_tokens_lifecycle(client):
    # Generate a token via pairing.
    code = client.post("/api/marketplace/pair/code").json()["code"]
    token = client.post("/api/bridge/pair/complete", json={"code": code}).json()["token"]
    tokens = client.get("/api/marketplace/tokens").json()["tokens"]
    assert len(tokens) == 1
    # Revoke.
    r = client.delete(f"/api/marketplace/tokens/{tokens[0]['id']}")
    assert r.status_code == 200
    # Token is marked revoked (not deleted), so a call with it now fails.
    who = client.get("/api/bridge/whoami", headers={"Authorization": f"Bearer {token}"})
    assert who.status_code == 401


# ---- End-to-end via stub: publish → search → install → approve ----


def test_e2e_marketplace_flow(client):
    _ensure_skill()
    # 1. Publish.
    pub = client.post(
        "/api/marketplace/publish",
        json={"skill_name": "skill-creator", "title": "SC", "description": "meta skill", "tags": ["meta"]},
    ).json()
    listing_id = pub["listing"]["id"]
    # 2. Search.
    results = client.get("/api/marketplace/search?q=meta").json()["results"]
    assert any(r["id"] == listing_id for r in results)
    # 3. Install from marketplace.
    inst = client.post("/api/marketplace/install", json={"listing_id": listing_id}).json()
    approval_id = inst["pending_approval"]
    # 4. Approve.
    approved = client.post(f"/api/marketplace/pending/{approval_id}/approve", json={"overwrite": True}).json()
    assert approved["installed"] is True
    # 5. Skill is in the registry.
    skills = client.get("/api/registry/skills").json()["skills"]
    assert any(s["name"] == "skill-creator" for s in skills)
