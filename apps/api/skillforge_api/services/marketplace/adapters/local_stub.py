"""LocalStubAdapter — an offline, filesystem-backed fake marketplace.

Lets the entire publish → search → download → install flow work today with no
website. Listings live at ``~/.skillforge/marketplace_stub/``:
  - ``index.json``      — listing metadata (id → Listing dict)
  - ``<id>.skillpkg``   — the packaged bundle for download

This is the reference implementation of ``MarketplaceAdapter`` and the spec the
real SkillForge Marketplace website must satisfy.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from threading import RLock
from typing import Any

from .base import Listing  # noqa: F401  (re-exported via __init__)


class LocalStubAdapter:
    """Offline marketplace backed by a local directory."""

    def __init__(self, root: str | Path | None = None) -> None:
        if root is not None:
            self._root = Path(root)
        else:
            self._root = Path.home() / ".skillforge" / "marketplace_stub"
        self._lock = RLock()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    # ---- index ----
    def _index_path(self) -> Path:
        return self._root / "index.json"

    def _load_index(self) -> dict[str, dict[str, Any]]:
        p = self._index_path()
        if not p.is_file():
            return {}
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return data.get("listings", {}) if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _save_index(self, listings: dict[str, dict[str, Any]]) -> None:
        self._index_path().write_text(
            json.dumps({"listings": listings}, indent=2), encoding="utf-8"
        )

    def _listing_id(self, skill_name: str, package_bytes: bytes) -> str:
        # Stable id keyed ONLY on the skill name, so re-publishing the same
        # skill updates the existing listing instead of creating duplicates.
        # (The package hash used to be part of the id; that produced a new row
        # every publish — the Browse panel would show the same skill N times.)
        return f"{skill_name}"

    @staticmethod
    def _is_listing_for(name: str, listing_id: str) -> bool:
        """True if ``listing_id`` refers to ``name`` (current or legacy id)."""
        if listing_id == name:
            return True
        # Legacy ids looked like "skill-name-<8 hex chars>".
        return bool(re.fullmatch(rf"{re.escape(name)}-[0-9a-f]{{8}}", listing_id))

    # ---- adapter protocol ----
    def publish(
        self,
        *,
        skill_name: str,
        package_bytes: bytes,
        listing_meta: dict[str, Any],
    ) -> Listing:
        with self._lock:
            listing_id = self._listing_id(skill_name, package_bytes)
            listings = self._load_index()

            # Sweep legacy/stale entries for the same skill name. Older versions
            # keyed the id on a content hash, so re-publishing left duplicates;
            # remove those now so a re-publish also cleans the index.
            stale_ids = [
                lid
                for lid in list(listings.keys())
                if lid != listing_id and self._is_listing_for(skill_name, lid)
            ]
            for lid in stale_ids:
                listings.pop(lid, None)
                (self._root / f"{lid}.skillpkg").unlink(missing_ok=True)

            # Store the bundle.
            (self._root / f"{listing_id}.skillpkg").write_bytes(package_bytes)
            # Build/update the listing.
            existing = listings.get(listing_id, {})
            downloads = existing.get("downloads", 0)
            listing = Listing(
                id=listing_id,
                name=skill_name,
                title=listing_meta.get("title", skill_name),
                description=listing_meta.get("description", ""),
                version=listing_meta.get("version", "0.1.0"),
                author=listing_meta.get("author", "you"),
                tags=listing_meta.get("tags"),
                license=listing_meta.get("license", "MIT"),
                price_usd=float(listing_meta.get("price_usd", 0.0)),
                rating=existing.get("rating", 0.0),
                reviews_count=existing.get("reviews_count", 0),
                downloads=downloads,
            )
            listings[listing_id] = listing.to_dict()
            self._save_index(listings)
            return listing

    def search(self, query: str = "", tags: list[str] | None = None) -> list[Listing]:
        with self._lock:
            listings = self._load_index()
            q = (query or "").lower()
            results: list[Listing] = []
            for data in listings.values():
                haystack = (
                    f"{data.get('name','')} {data.get('title','')} "
                    f"{data.get('description','')} {' '.join(data.get('tags') or [])}"
                ).lower()
                if q and q not in haystack:
                    continue
                if tags:
                    item_tags = {t.lower() for t in (data.get("tags") or [])}
                    if not item_tags.intersection({t.lower() for t in tags}):
                        continue
                results.append(Listing(**{k: v for k, v in data.items() if k != "free"}))
            # Sort by downloads desc, then name.
            results.sort(key=lambda x: (-x.downloads, x.name))
            return results

    def get(self, listing_id: str) -> Listing | None:
        with self._lock:
            data = self._load_index().get(listing_id)
            if not data:
                return None
            return Listing(**{k: v for k, v in data.items() if k != "free"})

    def download(self, listing_id: str) -> bytes:
        with self._lock:
            bundle = self._root / f"{listing_id}.skillpkg"
            if not bundle.is_file():
                raise FileNotFoundError(f"No package for listing {listing_id!r}")
            # Bump download count.
            listings = self._load_index()
            if listing_id in listings:
                listings[listing_id]["downloads"] = int(listings[listing_id].get("downloads", 0)) + 1
                self._save_index(listings)
            return bundle.read_bytes()

    def delete(self, listing_id: str) -> bool:
        with self._lock:
            listings = self._load_index()
            if listing_id not in listings:
                return False
            del listings[listing_id]
            self._save_index(listings)
            (self._root / f"{listing_id}.skillpkg").unlink(missing_ok=True)
            return True


# ---- singleton ----
_adapter: LocalStubAdapter | Any | None = None


def get_adapter():
    """Return the configured marketplace adapter (LocalStub by default)."""
    global _adapter
    if _adapter is None:
        from ....settings import get_settings

        kind = get_settings().marketplace_adapter or "local-stub"
        if kind == "local-stub":
            _adapter = LocalStubAdapter()
        else:
            # Unknown → fall back to stub so the app stays usable.
            _adapter = LocalStubAdapter()
    return _adapter


def set_adapter(adapter) -> None:
    """Override the singleton (tests pass a temp-dir adapter)."""
    global _adapter
    _adapter = adapter
