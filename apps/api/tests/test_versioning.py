"""Tests for semantic version bumping and skill re-install versioning."""

from __future__ import annotations

import pytest

from skillforge_api.services.versioning import (
    bump_version,
    classify_change,
    next_version_for_change,
    parse_version,
)


def test_parse_version():
    assert parse_version("1.2.3") == (1, 2, 3)
    assert parse_version("v0.1.0") == (0, 1, 0)
    assert parse_version("garbage") is None
    assert parse_version("") is None


def test_bump_patch():
    assert bump_version("0.1.0", "patch") == "0.1.1"
    assert bump_version("1.2.9", "patch") == "1.2.10"


def test_bump_minor_resets_patch():
    assert bump_version("0.1.7", "minor") == "0.2.0"
    assert bump_version("1.9.9", "minor") == "1.10.0"


def test_bump_major_resets_minor_and_patch():
    assert bump_version("2.3.4", "major") == "3.0.0"


def test_bump_invalid_version_falls_back():
    assert bump_version("not-a-version", "patch") == "0.1.1"


def test_classify_identity_change_is_major():
    b = classify_change(
        old_name="a-b", new_name="a-c", old_domain="x", new_domain="x",
        old_tool_names=[], new_tool_names=[], text_changed=False,
    )
    assert b.level == "major"


def test_classify_domain_change_is_major():
    b = classify_change(
        old_name="a-b", new_name="a-b", old_domain="Backend", new_domain="DevOps",
        old_tool_names=[], new_tool_names=[], text_changed=False,
    )
    assert b.level == "major"


def test_classify_tool_change_is_minor():
    b = classify_change(
        old_name="a-b", new_name="a-b", old_domain="x", new_domain="x",
        old_tool_names=["Python", "FastAPI"], new_tool_names=["Python", "Django"],
        text_changed=False,
    )
    assert b.level == "minor"


def test_classify_text_only_is_patch():
    b = classify_change(
        old_name="a-b", new_name="a-b", old_domain="x", new_domain="x",
        old_tool_names=["Python"], new_tool_names=["Python"],
        text_changed=True,
    )
    assert b.level == "patch"


def test_classify_no_change_is_patch():
    b = classify_change(
        old_name="a-b", new_name="a-b", old_domain="x", new_domain="x",
        old_tool_names=["Python"], new_tool_names=["Python"],
        text_changed=False,
    )
    assert b.level == "patch"


def test_next_version_for_change():
    b = classify_change(
        old_name="a-b", new_name="a-b", old_domain="x", new_domain="x",
        old_tool_names=["Python"], new_tool_names=["Python", "Redis"],
        text_changed=False,
    )
    assert next_version_for_change("0.1.0", b) == "0.2.0"
