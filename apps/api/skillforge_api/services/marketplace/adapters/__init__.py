"""Marketplace adapters.

A ``MarketplaceAdapter`` is the interface between local SkillForge and a
marketplace backend (today: a local offline stub; tomorrow: the real
SkillForge Marketplace website). The local UI and the bridge router both talk
to whichever adapter is configured.
"""

from .base import Listing, MarketplaceAdapter
from .local_stub import LocalStubAdapter, get_adapter, set_adapter

__all__ = ["Listing", "MarketplaceAdapter", "LocalStubAdapter", "get_adapter", "set_adapter"]
