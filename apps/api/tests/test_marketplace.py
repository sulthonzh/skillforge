"""Tests for the marketplace: pairing, packaging, stub adapter, bridge auth, approvals."""

from __future__ import annotations

import json
import os
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


# ---------------------------------------------------------------------------
# Isolation
#
# Every marketplace store (pairing tokens, approvals, listings) defaults to a
# file under ~/.skillforge. Without isolation the test suite would (and did)
# pollute the user's real config — e.g. each run appended duplicate bridge
# tokens to ~/.skillforge/marketplace_tokens.json. These fixtures redirect all
# three stores to a per-test temp dir and point the app singletons at them.
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_stores(tmp_path, monkeypatch):
    """Redirect ALL marketplace stores + app singletons into tmp_path.

    Returns the tmp_path so tests that need a direct PairingManager/adapter can
    construct one against the same path.
    """
    # Make HOME point at the temp dir so even code that builds paths from
    # Path.home() (the default for all three stores) lands in tmp_path.
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    # Fresh singletons backed by the temp dir.
    pairing = PairingManager(path=tmp_path / "marketplace_tokens.json")
    approvals = ApprovalManager(path=tmp_path / "marketplace_approvals.json")
    adapter = LocalStubAdapter(root=tmp_path / "marketplace_stub")
    set_pairing_manager(pairing)
    set_approval_manager(approvals)
    set_adapter(adapter)

    # Reset the pairing rate limiter so tests that drive pairing repeatedly
    # (the e2e flow, the tokens-lifecycle test, etc.) aren't throttled by a
    # previous test's budget.
    from skillforge_api.rate_limit import set_pairing_limiter, RateLimiter

    set_pairing_limiter(RateLimiter(limit=1000, window_seconds=60.0))

    yield tmp_path

    # Restore the real singletons so we don't leak into other test modules.
    set_pairing_manager(None)
    set_approval_manager(None)
    set_adapter(None)
    set_pairing_limiter(None)


@pytest.fixture
def client(isolated_stores):
    """A TestClient whose marketplace stores are isolated to tmp_path."""
    return TestClient(create_app())


def _ensure_skill():
    bootstrap_skill_creator()


# ---- PairingManager ----


def test_pairing_code_generated_and_single_use(isolated_stores):
    mgr = PairingManager()  # picks up tmp_path via Path.home() monkeypatch
    code = mgr.generate_code()
    assert len(code) == 6
    result = mgr.complete_pairing(code)
    assert result is not None
    plaintext, info = result
    assert len(plaintext) > 20
    assert "registry:read" in info.scopes
    # Single-use: second attempt fails.
    assert mgr.complete_pairing(code) is None


def test_pairing_invalid_code_returns_none(isolated_stores):
    assert PairingManager().complete_pairing("BOGUS0") is None


def test_token_validate_and_revoke(isolated_stores):
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


def test_token_wrong_secret_fails(isolated_stores):
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


def test_stub_publish_search_download(isolated_stores):
    _ensure_skill()
    adapter = LocalStubAdapter()  # isolated via Path.home() monkeypatch
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


def test_stub_search_empty(isolated_stores):
    assert LocalStubAdapter().search("nothing") == []


def test_stub_delete(isolated_stores):
    _ensure_skill()
    adapter = LocalStubAdapter()  # isolated via Path.home() monkeypatch
    pkg = SkillPackager().pack("skill-creator")
    listing = adapter.publish(skill_name="skill-creator", package_bytes=pkg, listing_meta={})
    assert adapter.delete(listing.id) is True
    assert adapter.get(listing.id) is None
    assert adapter.delete(listing.id) is False


# ---- LocalStubAdapter: re-publish dedup (regression for duplicate listings) ----


def test_stub_republish_same_skill_does_not_duplicate(tmp_path):
    """Re-publishing the same skill must update, not create a new listing.

    Regression: the listing id used to be keyed on a content hash, so every
    publish created a new row and the Browse panel showed the same skill N
    times. The id must be stable across re-publishes.
    """
    adapter = LocalStubAdapter(root=tmp_path)

    pkg_v1 = b"package bytes v1"
    l1 = adapter.publish(
        skill_name="my-skill",
        package_bytes=pkg_v1,
        listing_meta={"version": "0.1.0", "title": "My Skill"},
    )

    pkg_v2 = b"package bytes v2 (different content, e.g. new version)"
    l2 = adapter.publish(
        skill_name="my-skill",
        package_bytes=pkg_v2,
        listing_meta={"version": "0.2.0", "title": "My Skill"},
    )

    # Same listing id → updated in place, not duplicated.
    assert l1.id == l2.id
    assert l2.version == "0.2.0"
    # Exactly one listing in the index.
    results = adapter.search("")
    assert len([r for r in results if r.name == "my-skill"]) == 1


def test_stub_republish_sweeps_legacy_hashed_ids(tmp_path):
    """A pre-fix index.json with legacy '<name>-<hash>' ids gets cleaned up.

    Simulates a user who already has duplicate listings from before the fix:
    on next publish, the stale legacy entries for the same skill must be
    removed so the Browse panel stops showing duplicates.
    """
    adapter = LocalStubAdapter(root=tmp_path)

    # Seed the index as it looked BEFORE the fix: three legacy-hash ids for
    # the same skill name (exactly the bug the user hit on the marketplace page).
    index_path = tmp_path / "index.json"
    index_path.write_text(
        json.dumps(
            {
                "listings": {
                    "skill-creator-aabbccdd": {
                        "id": "skill-creator-aabbccdd",
                        "name": "skill-creator",
                        "title": "Skill Creator",
                        "description": "old v1",
                        "version": "0.1.0",
                        "author": "you",
                        "tags": [],
                        "license": "MIT",
                        "price_usd": 0.0,
                        "rating": 0.0,
                        "reviews_count": 0,
                        "downloads": 3,
                    },
                    "skill-creator-11223344": {
                        "id": "skill-creator-11223344",
                        "name": "skill-creator",
                        "title": "Skill Creator",
                        "description": "old v2",
                        "version": "0.2.0",
                        "author": "you",
                        "tags": [],
                        "license": "MIT",
                        "price_usd": 0.0,
                        "rating": 0.0,
                        "reviews_count": 0,
                        "downloads": 1,
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    # Stale bundle files that match the legacy ids.
    (tmp_path / "skill-creator-aabbccdd.skillpkg").write_bytes(b"old v1")
    (tmp_path / "skill-creator-11223344.skillpkg").write_bytes(b"old v2")

    # Re-publish — this must collapse to a single listing.
    adapter.publish(
        skill_name="skill-creator",
        package_bytes=b"new package v3",
        listing_meta={"version": "0.3.0", "title": "Skill Creator"},
    )

    results = adapter.search("")
    creator_results = [r for r in results if r.name == "skill-creator"]
    assert len(creator_results) == 1
    assert creator_results[0].version == "0.3.0"
    # The stale bundle files are gone.
    assert not (tmp_path / "skill-creator-aabbccdd.skillpkg").exists()
    assert not (tmp_path / "skill-creator-11223344.skillpkg").exists()


def test_stub_legacy_id_detection_does_not_clobber_unrelated(tmp_path):
    """The legacy-id sweep must only remove entries for the SAME skill name."""
    adapter = LocalStubAdapter(root=tmp_path)
    adapter.publish(
        skill_name="skill-a", package_bytes=b"a", listing_meta={}
    )
    adapter.publish(
        skill_name="skill-b", package_bytes=b"b", listing_meta={}
    )
    # Re-publish skill-a — skill-b must survive.
    adapter.publish(
        skill_name="skill-a", package_bytes=b"a-v2", listing_meta={"version": "0.2.0"}
    )
    names = sorted(r.name for r in adapter.search(""))
    assert names == ["skill-a", "skill-b"]


# ---- ApprovalManager ----


def test_approval_lifecycle(isolated_stores):
    mgr = ApprovalManager()  # isolated via Path.home() monkeypatch
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


# ---- Isolation guard ----


def test_marketplace_tests_do_not_write_to_real_config(isolated_stores, client):
    """Regression: the marketplace test suite must not pollute the user's real
    ~/.skillforge store.

    Before isolation, every test run appended bridge tokens to the real
    marketplace_tokens.json (the user saw 28+ duplicate "marketplace" tokens)
    and left approval records in marketplace_approvals.json. This test exercises
    the full write path (pair → complete → publish → install → approve) and then
    asserts that the REAL home directory's store files were never touched.
    """
    import os
    from pathlib import Path

    # Restore the REAL home (isolated_stores monkeypatched Path.home to tmp_path;
    # we need the genuine one to inspect it). We read the env directly because
    # re-patching Path.home mid-test would break the client's isolated stores.
    real_home = Path(os.environ["HOME"])

    # Snapshot the real store files BEFORE driving writes through the client.
    real_tokens = real_home / ".skillforge" / "marketplace_tokens.json"
    real_approvals = real_home / ".skillforge" / "marketplace_approvals.json"

    def _count(p: Path) -> int:
        if not p.is_file():
            return 0
        try:
            return len(json.loads(p.read_text()).get("tokens") or
                       json.loads(p.read_text()).get("approvals") or [])
        except Exception:
            return -1

    tokens_before = _count(real_tokens)
    approvals_before = _count(real_approvals)

    # Drive the full write path through the isolated client.
    _ensure_skill()
    code = client.post("/api/marketplace/pair/code").json()["code"]
    client.post("/api/bridge/pair/complete", json={"code": code})
    client.post("/api/marketplace/publish", json={"skill_name": "skill-creator"})
    listing_id = client.post(
        "/api/marketplace/publish", json={"skill_name": "skill-creator"}
    ).json()["listing"]["id"]
    inst = client.post("/api/marketplace/install", json={"listing_id": listing_id}).json()
    client.post(f"/api/marketplace/pending/{inst['pending_approval']}/approve", json={"overwrite": True})

    # The real store files must be unchanged.
    assert _count(real_tokens) == tokens_before, (
        "marketplace_tokens.json was polluted by the test client — isolation is broken"
    )
    assert _count(real_approvals) == approvals_before, (
        "marketplace_approvals.json was polluted by the test client — isolation is broken"
    )
