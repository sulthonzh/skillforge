"""Approval queue for marketplace-originated installs.

Marketplace installs must be confirmed by the user (unless the bridge token has
the explicit ``skills:install:unattended`` scope, off by default). A
marketplace install creates a pending ``Approval``; the user approves (→ the
skill is installed) or rejects (→ discarded) from the UI.
"""

from __future__ import annotations

import enum
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

import secrets


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class Approval:
    id: str
    skill_name: str
    source: str  # "marketplace:<listing_id>" or "bridge"
    manifest_json: str  # the SkillManifest as JSON
    status: str  # ApprovalStatus value
    created_at: str  # ISO

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ApprovalManager:
    """In-memory + JSON-backed approval queue."""

    def __init__(self, path: str | Path | None = None) -> None:
        if path is not None:
            self._path = Path(path)
        else:
            self._path = Path.home() / ".skillforge" / "marketplace_approvals.json"
        self._lock = RLock()
        self._cache: list[Approval] | None = None

    @property
    def path(self) -> Path:
        return self._path

    def create(self, skill_name: str, manifest_json: str, source: str = "marketplace") -> Approval:
        with self._lock:
            self._load()
            approval = Approval(
                id=secrets.token_hex(8),
                skill_name=skill_name,
                source=source,
                manifest_json=manifest_json,
                status=ApprovalStatus.PENDING.value,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            assert self._cache is not None
            self._cache.append(approval)
            self._write()
            return approval

    def list_pending(self) -> list[Approval]:
        with self._lock:
            self._load()
            assert self._cache is not None
            return [a for a in self._cache if a.status == ApprovalStatus.PENDING.value]

    def get(self, approval_id: str) -> Approval | None:
        with self._lock:
            self._load()
            assert self._cache is not None
            return next((a for a in self._cache if a.id == approval_id), None)

    def set_status(self, approval_id: str, status: ApprovalStatus) -> Approval | None:
        with self._lock:
            self._load()
            assert self._cache is not None
            for a in self._cache:
                if a.id == approval_id:
                    a.status = status.value
                    self._write()
                    return a
            return None

    def reset_cache(self) -> None:
        with self._lock:
            self._cache = None

    def _load(self) -> None:
        if self._cache is not None:
            return
        if not self._path.is_file():
            self._cache = []
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            items = data.get("approvals", []) if isinstance(data, dict) else []
            self._cache = [Approval(**i) for i in items if isinstance(i, dict)]
        except (json.JSONDecodeError, TypeError):
            self._cache = []

    def _write(self) -> None:
        assert self._cache is not None
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps({"approvals": [a.to_dict() for a in self._cache]}, indent=2),
            encoding="utf-8",
        )


# ---- singleton ----
_manager: ApprovalManager | None = None


def get_approval_manager() -> ApprovalManager:
    global _manager
    if _manager is None:
        _manager = ApprovalManager()
    return _manager


def set_approval_manager(mgr: ApprovalManager | None) -> None:
    global _manager
    _manager = mgr
