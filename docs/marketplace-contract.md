# SkillForge Marketplace — Local Bridge API Contract

This document specifies the wire contract between the **SkillForge Marketplace
website** (a separate cloud project) and the **local SkillForge** instance
running on a user's machine. The local OSS app implements this contract today;
the marketplace website must implement its side to interoperate.

## Overview

```
┌─────────────────────────┐         ┌──────────────────────────┐
│  Marketplace website     │  HTTPS  │  Local SkillForge :8000   │
│  (cloud, separate proj)  │ ──────► │  (user's machine)         │
│                          │  bridge │                           │
│  accounts, listings,     │  token  │  /api/bridge/* (gated)    │
│  payments, reviews        │         │  /api/marketplace/* (UI)  │
└─────────────────────────┘         └──────────────────────────┘
```

The user's browser is on the marketplace site. The site's JavaScript makes
fetch calls to the user's `localhost:8000` (the **bridge**) to install skills
locally. This requires a **pairing flow** so only an authorized marketplace
session can reach the local API.

## 1. Pairing flow (VS Code + GitHub pattern)

1. The local SkillForge user opens **/marketplace → Connection → Generate pairing code**.
2. SkillForge returns a **6-character, single-use code** (TTL 10 minutes):
   ```
   POST /api/marketplace/pair/code → {"code": "AB3X9K", "ttl_minutes": 10}
   ```
3. The user enters the code on the marketplace website.
4. The marketplace site calls:
   ```
   POST /api/bridge/pair/complete
   Body: {"code": "AB3X9K", "label": "skillforge-marketplace"}
   → 200: {"token": "<32-byte-urlsafe-secret>", "token_id": "...", "scopes": [...]}
   → 401: invalid/expired/used code
   ```
5. The marketplace stores the token and sends it as
   `Authorization: Bearer <token>` on every subsequent bridge call.

**The token is returned exactly once. SkillForge stores only its sha256 hash.**

## 2. Bridge endpoints (all under `/api/bridge`, bearer-token-gated)

| Method | Path | Scope | Purpose |
|--------|------|-------|---------|
| `POST` | `/pair/complete` | _(code)_ | Exchange a pairing code for a token |
| `GET` | `/whoami` | any | Validate token; return scopes |
| `GET` | `/skills` | `registry:read` | List locally installed skills |
| `POST` | `/skills/publish` | `skills:publish` | Package + push a local skill to the marketplace |
| `POST` | `/skills/install` | `skills:install` | Install a skill locally (queued for user approval) |
| `GET` | `/pending` | any | List pending marketplace-originated installs |
| `POST` | `/pending/{id}/approve` | any | Approve a pending install |
| `POST` | `/pending/{id}/reject` | any | Reject a pending install |

### Scopes

| Scope | Granted by default | Purpose |
|-------|--------------------|---------|
| `registry:read` | ✅ | Read installed skills |
| `skills:install` | ✅ | Queue an install (requires user approval) |
| `skills:publish` | ✅ | Package + upload a local skill |
| `skills:install:unattended` | ❌ | Install without user approval (automation only) |

### Install behavior

By default, `POST /api/bridge/skills/install` creates a **pending approval** —
the local user must click Approve. This prevents the marketplace from silently
installing anything. Unattended installs require the
`skills:install:unattended` scope AND `{"unattended": true}` in the body.

## 3. `.skillpkg` format (the wire bundle)

A `.skillpkg` is a **gzipped tarball**:

```
skill-creator.skillpkg
├── PACKAGING        # JSON: {name, version, packaged_at, packaged_by}
├── manifest.json    # The SkillManifest (canonical JSON)
├── SKILL.md
├── README.md
├── config.yaml
├── prompts/
├── templates/
├── scripts/
└── examples/
```

`manifest.json` is the source of truth. Paths in the tarball are relative;
absolute paths and `..` traversal are rejected on unpack.

## 4. Listing metadata

The marketplace stores listing metadata (title, description, tags, license,
price, author, rating, reviews). Locally we only carry these fields for display:

```json
{
  "id": "skill-creator-a1b2c3d4",
  "name": "skill-creator",
  "title": "Skill Creator",
  "description": "Helps engineers author new skills.",
  "version": "0.1.0",
  "author": "you",
  "tags": ["meta"],
  "license": "MIT",
  "price_usd": 0.0,
  "free": true,
  "rating": 4.5,
  "reviews_count": 12,
  "downloads": 42
}
```

## 5. `MarketplaceAdapter` protocol

The marketplace website backend must satisfy this interface (the
`LocalStubAdapter` in `services/marketplace/adapters/local_stub.py` is the
reference implementation):

```python
class MarketplaceAdapter(Protocol):
    def publish(self, *, skill_name: str, package_bytes: bytes,
                listing_meta: dict) -> Listing: ...
    def search(self, query: str = "", tags: list[str] | None = None) -> list[Listing]: ...
    def get(self, listing_id: str) -> Listing | None: ...
    def download(self, listing_id: str) -> bytes: ...
    def delete(self, listing_id: str) -> bool: ...
```

## 6. Security guarantees

- **Pairing codes** are 6 chars, single-use, 10-min TTL.
- **Bridge tokens** are 32-byte URL-safe secrets; only the sha256 hash is stored locally (chmod 600).
- **Tokens are revocable** from the local UI at any time.
- **CORS** is scoped to explicit localhost origins + the configured marketplace origin (never `*`).
- **Localhost bind by default** (`127.0.0.1`) — not LAN-exposed.
- **No auto-execution** — bridge installs write files only; they never run scripts.
- **User approval required** for marketplace installs unless an explicit unattended scope is granted.
- **No payment data** touches the local app — selling is the marketplace site's job; locally we carry `price`/`license` metadata only.

## 7. Local testing (no website needed)

The `LocalStubAdapter` (`marketplace_adapter=local-stub`) implements the full
publish → search → download → install flow offline. Open `/marketplace` to
publish a skill, search for it, click Install, and approve — all locally.
