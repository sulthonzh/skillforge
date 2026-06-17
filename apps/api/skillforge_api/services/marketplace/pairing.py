"""Pairing codes + bridge tokens.

The pairing flow (VS Code + GitHub pattern):
  1. Local SkillForge generates a short-lived (10 min), single-use 6-char code.
  2. The marketplace site (or the local UI for testing) POSTs the code to
     /api/bridge/pair/complete and receives a scoped bridge token.
  3. The marketplace sends the token as `Authorization: Bearer <token>` on every
     bridge call. Tokens are revocable + scoped + stored hashed.

Tokens live at ``~/.skillforge/marketplace_tokens.json`` (chmod 600). The
plaintext secret is returned exactly once (at pairing time) and never stored.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import string
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from ...settings import get_settings

CODE_TTL_MINUTES = 10
CODE_ALPHABET = string.ascii_uppercase + string.digits  # no ambiguous chars
CODE_LENGTH = 6

# Default scopes granted to a freshly-paired marketplace token. The marketplace
# can read the registry, install skills (with user approval), and publish.
DEFAULT_SCOPES = ("registry:read", "skills:install", "skills:publish")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class PendingCode:
    code: str
    created_at: datetime
    label: str


@dataclass
class TokenInfo:
    """A persisted bridge token. The plaintext secret is NEVER stored."""

    id: str
    secret_hash: str  # sha256 hex of the plaintext token
    scopes: list[str]
    label: str
    created_at: str  # ISO
    last_used_at: str | None = None
    revoked: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PairingManager:
    """Generate pairing codes and mint/validate bridge tokens."""

    def __init__(self, path: str | Path | None = None) -> None:
        if path is not None:
            self._path = Path(path)
        else:
            self._path = Path.home() / ".skillforge" / "marketplace_tokens.json"
        self._lock = RLock()
        # Pending codes live in-memory only (short-lived, single-use).
        self._pending: dict[str, PendingCode] = {}
        self._tokens_cache: list[TokenInfo] | None = None

    @property
    def path(self) -> Path:
        return self._path

    # ---- pairing codes ----
    def generate_code(self, label: str = "marketplace") -> str:
        """Generate a short-lived, single-use pairing code. Returns the code."""
        with self._lock:
            # Expire stale codes.
            self._prune_pending()
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
            self._pending[code] = PendingCode(code=code, created_at=_utcnow(), label=label)
            return code

    def _prune_pending(self) -> None:
        cutoff = _utcnow() - timedelta(minutes=CODE_TTL_MINUTES)
        stale = [c for c, p in self._pending.items() if p.created_at < cutoff]
        for c in stale:
            del self._pending[c]

    def pending_codes(self) -> list[dict[str, Any]]:
        with self._lock:
            self._prune_pending()
            return [
                {"code": p.code, "label": p.label, "created_at": p.created_at.isoformat()}
                for p in self._pending.values()
            ]

    # ---- token minting ----
    def complete_pairing(self, code: str) -> tuple[str, TokenInfo] | None:
        """Exchange a pairing code for a bridge token.

        Returns ``(plaintext_token, token_info)`` on success, or ``None`` if the
        code is invalid/expired/used. The code is single-use.
        """
        with self._lock:
            self._prune_pending()
            pending = self._pending.pop(code, None)
            if pending is None:
                return None
            plaintext = secrets.token_urlsafe(32)
            info = TokenInfo(
                id=secrets.token_hex(8),
                secret_hash=hashlib.sha256(plaintext.encode()).hexdigest(),
                scopes=list(DEFAULT_SCOPES),
                label=pending.label,
                created_at=_utcnow().isoformat(),
            )
            self._load_tokens()
            assert self._tokens_cache is not None
            self._tokens_cache.append(info)
            self._write_tokens()
            return plaintext, info

    # ---- token validation ----
    def validate(self, plaintext: str) -> TokenInfo | None:
        """Validate a bearer token. Returns the TokenInfo if valid+active, else None."""
        if not plaintext:
            return None
        h = hashlib.sha256(plaintext.encode()).hexdigest()
        with self._lock:
            self._load_tokens()
            assert self._tokens_cache is not None
            for t in self._tokens_cache:
                if t.secret_hash == h and not t.revoked:
                    t.last_used_at = _utcnow().isoformat()
                    self._write_tokens()
                    return t
            return None

    def has_scope(self, plaintext: str, scope: str) -> bool:
        t = self.validate(plaintext)
        return t is not None and scope in t.scopes

    # ---- token management ----
    def list_tokens(self) -> list[TokenInfo]:
        with self._lock:
            self._load_tokens()
            assert self._tokens_cache is not None
            return [TokenInfo(**t.to_dict()) for t in self._tokens_cache]

    def revoke(self, token_id: str) -> bool:
        with self._lock:
            self._load_tokens()
            assert self._tokens_cache is not None
            for t in self._tokens_cache:
                if t.id == token_id:
                    t.revoked = True
                    self._write_tokens()
                    return True
            return False

    def reset_cache(self) -> None:
        with self._lock:
            self._tokens_cache = None

    # ---- persistence ----
    def _load_tokens(self) -> None:
        if self._tokens_cache is not None:
            return
        if not self._path.is_file():
            self._tokens_cache = []
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            tokens = data.get("tokens", []) if isinstance(data, dict) else []
            self._tokens_cache = [TokenInfo(**t) for t in tokens if isinstance(t, dict)]
        except (json.JSONDecodeError, TypeError):
            self._tokens_cache = []

    def _write_tokens(self) -> None:
        assert self._tokens_cache is not None
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {"tokens": [t.to_dict() for t in self._tokens_cache]},
            indent=2,
            default=str,
        )
        # Atomic write with restricted perms (the file proves pairing happened).
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(payload, encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        tmp.replace(self._path)
        try:
            os.chmod(self._path, 0o600)
        except OSError:
            pass


# ---- singleton ----
_manager: PairingManager | None = None


def get_pairing_manager() -> PairingManager:
    global _manager
    if _manager is None:
        _manager = PairingManager()
    return _manager


def set_pairing_manager(mgr: PairingManager | None) -> None:
    """Override the singleton (tests pass a temp-path manager)."""
    global _manager
    _manager = mgr
