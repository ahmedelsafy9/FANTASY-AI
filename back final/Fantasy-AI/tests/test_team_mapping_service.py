"""Unit tests for src.data_collection.services.team_mapping_service."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.data_collection.services.team_mapping_service import (
    TeamMappingService,
    resolve_numeric_opponent_column,
)


def test_build_mapping_creates_id_to_name_dict() -> None:
    """build_mapping must produce a clean int -> name dict from raw team records."""
    service = TeamMappingService(Path("/tmp/unused.json"))
    teams = [{"id": 1, "name": "Arsenal", "short_name": "ARS"}, {"id": 2, "name": "Chelsea"}]
    mapping = service.build_mapping(teams)
    assert mapping == {1: "Arsenal", 2: "Chelsea"}


def test_build_mapping_skips_incomplete_records() -> None:
    """A team record missing 'id' or 'name' must be skipped, not crash."""
    service = TeamMappingService(Path("/tmp/unused.json"))
    teams = [{"id": 1, "name": "Arsenal"}, {"id": 2}, {"name": "Missing ID"}]
    mapping = service.build_mapping(teams)
    assert mapping == {1: "Arsenal"}


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    """A saved mapping must load back identically."""
    cache_path = tmp_path / "team_mapping.json"
    service = TeamMappingService(cache_path)
    mapping = {1: "Arsenal", 2: "Chelsea"}
    service.save(mapping)

    loaded = service.load()
    assert loaded == mapping


def test_load_returns_none_when_no_cache_exists(tmp_path: Path) -> None:
    """load() must return None gracefully when nothing has been cached yet."""
    service = TeamMappingService(tmp_path / "missing.json")
    assert service.load() is None


def test_load_returns_none_for_corrupt_cache(tmp_path: Path) -> None:
    """A corrupt cache file must not crash load() — it should return None."""
    cache_path = tmp_path / "team_mapping.json"
    cache_path.write_text("not valid json{{{")
    service = TeamMappingService(cache_path)
    assert service.load() is None


# --- resolve_numeric_opponent_column ------------------------------------------


def test_resolve_numeric_opponent_column_maps_known_ids() -> None:
    """Numeric IDs present in the mapping must resolve to team names."""
    df = pd.DataFrame({"opponent_team": [11, 6, 11]})
    resolved, count = resolve_numeric_opponent_column(
        df, "opponent_team", {11: "Arsenal", 6: "Chelsea"}
    )
    assert resolved.tolist() == ["Arsenal", "Chelsea", "Arsenal"]
    assert count == 3


def test_resolve_numeric_opponent_column_leaves_names_untouched() -> None:
    """Already-string values (team names) must not be altered."""
    df = pd.DataFrame({"opponent_team": ["Arsenal", "Chelsea"]})
    resolved, count = resolve_numeric_opponent_column(df, "opponent_team", {11: "Arsenal"})
    assert resolved.tolist() == ["Arsenal", "Chelsea"]
    assert count == 0


def test_resolve_numeric_opponent_column_leaves_unmapped_ids_as_is() -> None:
    """A numeric ID with no entry in the mapping must be left unresolved, not guessed."""
    df = pd.DataFrame({"opponent_team": [11, 999]})
    resolved, count = resolve_numeric_opponent_column(df, "opponent_team", {11: "Arsenal"})
    assert resolved.iloc[0] == "Arsenal"
    assert resolved.iloc[1] == 999  # left as the original numeric value
    assert count == 1


def test_resolve_numeric_opponent_column_handles_pure_int_dtype_column() -> None:
    """A column that is entirely numeric (int64 dtype) must not crash on string assignment.

    Regression test: pandas raises a dtype-casting error when assigning
    string values into a column whose dtype is still pure int64 unless
    the column is cast to object dtype first.
    """
    df = pd.DataFrame({"opponent_team": [11, 6, 11]})
    assert df["opponent_team"].dtype.kind in ("i", "u")  # confirm it's genuinely int-typed
    resolved, count = resolve_numeric_opponent_column(
        df, "opponent_team", {11: "Arsenal", 6: "Chelsea"}
    )
    assert resolved.tolist() == ["Arsenal", "Chelsea", "Arsenal"]
    assert count == 3
