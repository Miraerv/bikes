from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Iterable


def _load_json_store_ids(raw_store_ids: str | None) -> object | None:
    if not raw_store_ids:
        return None

    try:
        return cast("object", json.loads(raw_store_ids))
    except TypeError, ValueError:
        return None


def _coerce_store_id(value: object) -> int | None:
    if not isinstance(value, str | bytes | bytearray | int | float):
        return None

    try:
        return int(value)
    except TypeError, ValueError:
        return None


def _collect_store_ids(values: Iterable[object], *, skip_malformed: bool) -> list[int]:
    store_ids: list[int] = []
    for value in values:
        store_id = _coerce_store_id(value)
        if store_id is None:
            if skip_malformed:
                continue
            return []
        store_ids.append(store_id)
    return store_ids


def parse_store_id_list(raw_store_ids: str | None) -> list[int]:
    """Parse JSON store_ids for persisted supervisor assignments."""
    raw_ids = _load_json_store_ids(raw_store_ids)
    if not isinstance(raw_ids, list):
        return []

    return _collect_store_ids(cast("list[object]", raw_ids), skip_malformed=False)


def parse_store_id_set(raw_store_ids: str | None) -> set[int]:
    """Parse JSON store_ids into a set, ignoring malformed values."""
    raw_ids = _load_json_store_ids(raw_store_ids)
    if raw_ids is None:
        return set()

    if isinstance(raw_ids, list):
        values: Iterable[object] = cast("list[object]", raw_ids)
    else:
        values = [raw_ids]

    return set(_collect_store_ids(values, skip_malformed=True))


def dump_store_ids(store_ids: Iterable[int]) -> str:
    """Serialize sorted unique store ids for legacy string columns."""
    return json.dumps(sorted(set(store_ids)), ensure_ascii=True)
