"""Security tests: local-origin guard, rate limiting, constant-time comparison.

These cover the hardening added for the OSS release:
  * LocalOriginGuardMiddleware blocks browser requests from non-local origins
    (CSRF / DNS-rebinding defense for the token-less local endpoints).
  * RateLimiter caps pairing attempts so the 6-char code can't be brute-forced.
  * Token validation uses hmac.compare_digest (constant-time).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from skillforge_api.local_origin_guard import _is_local_origin
from skillforge_api.main import create_app
from skillforge_api.rate_limit import RateLimiter
from skillforge_api.services.marketplace.pairing import PairingManager


# ---------------------------------------------------------------------------
# LocalOriginGuardMiddleware
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(create_app())


def test_origin_parser_allows_loopback():
    assert _is_local_origin("http://localhost:3000") is True
    assert _is_local_origin("http://127.0.0.1:8000") is True
    assert _is_local_origin("http://[::1]:8000") is True


def test_origin_parser_blocks_remote():
    assert _is_local_origin("https://evil.com") is False
    assert _is_local_origin("http://attacker.example.com") is False
    assert _is_local_origin("http://192.168.1.5:8000") is False


def test_origin_parser_allows_absent_origin():
    """No origin header = not a browser request (curl, CLI) → allowed."""
    assert _is_local_origin(None) is True
    assert _is_local_origin("") is True


def test_middleware_blocks_remote_origin(client):
    """A request with a non-local Origin header is rejected with 403."""
    r = client.get("/health", headers={"Origin": "https://evil.com"})
    assert r.status_code == 403
    assert "non-local" in r.json()["detail"].lower()


def test_middleware_blocks_remote_referer(client):
    """Referer is checked too (some cross-origin requests carry it, not Origin)."""
    r = client.get("/health", headers={"Referer": "https://evil.com/page"})
    assert r.status_code == 403


def test_middleware_allows_local_origin(client):
    r = client.get("/health", headers={"Origin": "http://localhost:8000"})
    assert r.status_code == 200


def test_middleware_allows_no_origin(client):
    """curl / the CLI send no Origin header → allowed through."""
    r = client.get("/health")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# RateLimiter
# ---------------------------------------------------------------------------


def test_rate_limiter_allows_under_limit():
    rl = RateLimiter(limit=3, window_seconds=60.0)
    assert rl.allow("k") is True
    assert rl.allow("k") is True
    assert rl.allow("k") is True  # third hit allowed


def test_rate_limiter_blocks_over_limit():
    rl = RateLimiter(limit=3, window_seconds=60.0)
    for _ in range(3):
        rl.allow("k")
    assert rl.allow("k") is False  # fourth hit blocked
    assert rl.allow("k") is False


def test_rate_limiter_keys_are_independent():
    rl = RateLimiter(limit=1, window_seconds=60.0)
    assert rl.allow("a") is True
    assert rl.allow("b") is True  # different key, own budget
    assert rl.allow("a") is False  # 'a' exhausted
    assert rl.allow("b") is False  # 'b' exhausted


def test_rate_limiter_window_slides():
    """After the window elapses, the budget resets."""
    rl = RateLimiter(limit=1, window_seconds=0.05)  # 50ms window
    assert rl.allow("k") is True
    assert rl.allow("k") is False
    import time

    time.sleep(0.06)
    assert rl.allow("k") is True  # window slid, new budget


# ---------------------------------------------------------------------------
# Constant-time token validation
# ---------------------------------------------------------------------------


def test_token_validation_is_constant_time(tmp_path):
    """Validate must work correctly (functional check for the hmac.compare_digest fix).

    A true timing test would be flaky in CI; this confirms the happy + failure
    paths both return the right result after switching to compare_digest.
    """
    mgr = PairingManager(path=tmp_path / "tokens.json")
    code = mgr.generate_code()
    plaintext, info = mgr.complete_pairing(code)

    # Correct token validates.
    assert mgr.validate(plaintext) is not None
    # Wrong token fails (different length, different content).
    assert mgr.validate("wrong") is None
    assert mgr.validate("") is None
    assert mgr.validate(plaintext[:-1] + "X") is None
    # Revoked token fails.
    mgr.revoke(info.id)
    assert mgr.validate(plaintext) is None
