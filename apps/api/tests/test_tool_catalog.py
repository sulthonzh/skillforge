"""Tests for the tool catalog loader and matcher."""

from __future__ import annotations

import pytest

from skillforge_api.services.tool_catalog import (
    CatalogError,
    ToolCatalog,
    _contains_word,
    get_catalog,
    load_catalog,
)


def test_packaged_catalog_loads():
    catalog = load_catalog()
    assert isinstance(catalog, ToolCatalog)
    # The spec requires at least the four canonical domains.
    keys = set(catalog.domain_keys())
    assert {"backend", "data_engineering", "devops", "ai_engineering"} <= keys


def test_catalog_has_tools_per_domain():
    catalog = get_catalog()
    for key in catalog.domain_keys():
        cats = catalog.categories(key)
        assert cats, f"domain {key!r} has no categories"


def test_find_domain_backend():
    catalog = get_catalog()
    assert catalog.find_domain("I need a REST API in Python") == "backend"
    assert catalog.find_domain("data pipeline with airflow and dbt") == "data_engineering"
    assert catalog.find_domain("kubernetes helm terraform") == "devops"


def test_find_domain_empty_returns_none():
    assert get_catalog().find_domain("") is None


def test_find_tools_in_text_detects_with_punctuation():
    catalog = get_catalog()
    mentioned = catalog.find_tools_in_text(
        "I need a backend skill for FastAPI, PostgreSQL, Docker, and Pytest"
    )
    names = {name for name, _ in mentioned}
    assert {"FastAPI", "PostgreSQL", "Docker", "Pytest"} <= names


def test_find_tools_avoids_false_positive_go():
    catalog = get_catalog()
    mentioned = catalog.find_tools_in_text("I am going home now")
    names = {name for name, _ in mentioned}
    assert "Go" not in names


def test_contains_word_multiline_token():
    assert _contains_word("set up github actions for CI", "GitHub Actions")
    assert not _contains_word("no actions were taken", "GitHub Actions")


def test_malformed_catalog_raises(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(CatalogError):
        load_catalog(bad)


def test_catalog_all_tools_dedupes():
    catalog = get_catalog()
    tools = catalog.all_tools()
    # Each tool appears once even if listed in multiple domains.
    assert len(tools) == len(set(tools))
