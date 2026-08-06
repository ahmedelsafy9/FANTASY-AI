"""Unit tests for src.api.services.player_service.

These tests exercise PlayerService directly, with no FastAPI/HTTP
layer involved — the service is plain Python operating on a
DataFrame, so it's fully testable on its own.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.api.services.player_service import PlayerService
from src.core.exceptions import PlayerNotFoundError


def _sample_data() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "element": [1, 1, 2, 2],
            "name": ["Salah", "Salah", "Haaland", "Haaland"],
            "season": ["2022-23"] * 4,
            "GW": [1, 2, 1, 2],
            "total_points": [10, 6, 15, 9],
        }
    )


def test_get_player_returns_latest_row() -> None:
    """get_player must return the player's most recent (highest GW) row."""
    service = PlayerService(
        _sample_data(), player_id_columns=("element",), chronological_columns=("season", "GW")
    )
    player = service.get_player("1")
    assert player["GW"] == 2
    assert player["total_points"] == 6


def test_get_player_raises_for_unknown_id() -> None:
    """get_player must raise PlayerNotFoundError for an unmatched identifier."""
    service = PlayerService(
        _sample_data(), player_id_columns=("element",), chronological_columns=("season", "GW")
    )
    with pytest.raises(PlayerNotFoundError):
        service.get_player("999")


def test_get_player_matches_numeric_id_as_string() -> None:
    """A numeric player_id column must still match a string path-parameter id."""
    service = PlayerService(
        _sample_data(), player_id_columns=("element",), chronological_columns=("season", "GW")
    )
    player = service.get_player("2")
    assert player["name"] == "Haaland"


def test_get_player_result_has_no_nan_only_none() -> None:
    """NaN values in the row must be converted to None for JSON serialization."""
    df = _sample_data()
    df.loc[3, "total_points"] = float("nan")
    service = PlayerService(
        df, player_id_columns=("element",), chronological_columns=("season", "GW")
    )
    player = service.get_player("2")
    assert player["total_points"] is None


def test_list_player_ids_returns_all_unique_players() -> None:
    """list_player_ids must return one identifier per known player."""
    service = PlayerService(
        _sample_data(), player_id_columns=("element",), chronological_columns=("season", "GW")
    )
    ids = service.list_player_ids()
    assert set(ids) == {"1", "2"}


def test_player_service_raises_without_identifier_column() -> None:
    """Constructing the service without any usable identifier column must raise."""
    df = pd.DataFrame({"season": ["2022-23"], "GW": [1]})
    with pytest.raises(ValueError):
        PlayerService(df, player_id_columns=("element", "name"), chronological_columns=("season", "GW"))
