"""MarketplaceAdapter protocol + shared types.

The protocol is the contract the separate SkillForge Marketplace project must
implement. ``LocalStubAdapter`` is the reference implementation.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


class Listing:
    """A marketplace skill listing (metadata, not the bundle)."""

    def __init__(
        self,
        *,
        id: str,
        name: str,
        title: str,
        description: str,
        version: str,
        author: str,
        tags: list[str] | None = None,
        license: str = "MIT",
        price_usd: float = 0.0,
        rating: float = 0.0,
        reviews_count: int = 0,
        downloads: int = 0,
    ) -> None:
        self.id = id
        self.name = name
        self.title = title
        self.description = description
        self.version = version
        self.author = author
        self.tags = tags or []
        self.license = license
        self.price_usd = price_usd
        self.rating = rating
        self.reviews_count = reviews_count
        self.downloads = downloads

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "tags": self.tags,
            "license": self.license,
            "price_usd": self.price_usd,
            "free": self.price_usd <= 0.0,
            "rating": self.rating,
            "reviews_count": self.reviews_count,
            "downloads": self.downloads,
        }


@runtime_checkable
class MarketplaceAdapter(Protocol):
    """The interface a marketplace backend must implement."""

    def publish(
        self,
        *,
        skill_name: str,
        package_bytes: bytes,
        listing_meta: dict[str, Any],
    ) -> Listing:
        """Upload a packaged skill + create/update a listing."""
        ...

    def search(self, query: str = "", tags: list[str] | None = None) -> list[Listing]:
        """Search listings."""
        ...

    def get(self, listing_id: str) -> Listing | None:
        """Fetch one listing's metadata."""
        ...

    def download(self, listing_id: str) -> bytes:
        """Download a ``.skillpkg`` bundle. Returns the raw bytes."""
        ...

    def delete(self, listing_id: str) -> bool:
        """Remove a listing (seller-only; the local stub allows it)."""
        ...
