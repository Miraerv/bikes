# ruff: noqa: S101

from __future__ import annotations

from app.core.store_ids import dump_store_ids, parse_store_id_list, parse_store_id_set


def test_parse_store_id_list_requires_json_list() -> None:
    assert parse_store_id_list('[54, "55"]') == [54, 55]
    assert parse_store_id_list('"54"') == []


def test_parse_store_id_list_returns_empty_when_any_item_is_malformed() -> None:
    assert parse_store_id_list('[54, "bad"]') == []


def test_parse_store_id_set_ignores_malformed_values() -> None:
    assert parse_store_id_set('[54, "55", "bad"]') == {54, 55}
    assert parse_store_id_set('"56"') == {56}


def test_dump_store_ids_sorts_and_deduplicates() -> None:
    assert dump_store_ids([55, 54, 55]) == "[54, 55]"
