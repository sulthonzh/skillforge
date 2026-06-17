"""Bridge authentication — FastAPI dependency that validates a bridge token.

Used by the ``/api/bridge/*`` router. Extracts the ``Authorization: Bearer …``
header, validates the token via ``PairingManager``, checks the required scope,
and returns a ``BridgePrincipal`` (or raises 401/403).
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException

from .pairing import PairingManager, TokenInfo, get_pairing_manager


@dataclass
class BridgePrincipal:
    """The authenticated marketplace caller."""

    token_id: str
    label: str
    scopes: list[str]

    def can(self, scope: str) -> bool:
        return scope in self.scopes


def require_bridge(
    authorization: str | None = Header(default=None),
    manager: PairingManager = Depends(get_pairing_manager),
) -> BridgePrincipal:
    """Validate the bearer token. Returns the principal or raises 401."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    plaintext = authorization.split(" ", 1)[1].strip()
    info: TokenInfo | None = manager.validate(plaintext)
    if info is None:
        raise HTTPException(status_code=401, detail="Invalid or revoked token")
    return BridgePrincipal(token_id=info.id, label=info.label, scopes=info.scopes)


def require_scope(scope: str):
    """Build a dependency that also requires a specific scope (403 if missing)."""

    def _checker(principal: BridgePrincipal = Depends(require_bridge)) -> BridgePrincipal:
        if not principal.can(scope):
            raise HTTPException(
                status_code=403,
                detail=f"Token lacks required scope: {scope}",
            )
        return principal

    return _checker
