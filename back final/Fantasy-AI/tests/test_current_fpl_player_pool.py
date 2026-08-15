"""Unit tests for current FPL player/team pool derivation from bootstrap-static.

Verifies:
1. Current players are driven strictly by bootstrap-static `elements`.
2. Current player IDs match `elements[].id`.
3. Current team names resolve strictly via bootstrap-static `teams`.
4. Promoted team players (not present in historical Vaastav data) appear with predictions defaulted.
5. Relegated/historical players not present in current bootstrap-static `elements` disappear from the current squad pool.
6. Model predictions connect to current players via numeric ID / normalized name (LEFT JOIN).
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.api.state import _build_current_fpl_prediction_pool
from src.metadata.player_metadata import build_player_metadata
from src.metadata.team_metadata import build_team_metadata


@pytest.fixture
def mock_bootstrap_static():
    """Mock bootstrap-static payload with current season teams and players."""
    return {
        "teams": [
            {"id": 1, "name": "Arsenal", "short_name": "ARS", "code": 3},
            {"id": 2, "name": "Ipswich Town", "short_name": "IPS", "code": 40},  # Promoted team
        ],
        "elements": [
            {
                "id": 101,
                "web_name": "Saka",
                "first_name": "Bukayo",
                "second_name": "Saka",
                "team": 1,
                "element_type": 3,
                "now_cost": 100,
                "status": "a",
                "total_points": 150,
                "photo": "111.jpg",
            },
            {
                "id": 202,
                "web_name": "Delap",
                "first_name": "Liam",
                "second_name": "Delap",
                "team": 2,  # Promoted team player
                "element_type": 4,
                "now_cost": 55,
                "status": "a",
                "total_points": 40,
                "photo": "222.jpg",
            },
        ],
    }


@pytest.fixture
def mock_historical_model_predictions():
    """Model predictions derived from historical data (includes a relegated player)."""
    return pd.DataFrame([
        {
            "element": 101,
            "name": "Bukayo Saka",
            "name_normalized": "bukayo saka",
            "predicted_total_points": 6.8,
            "predicted_for_gw": 2,
            "opponent_team": "Chelsea",
            "is_home": 1,
            "fixture_difficulty": 3,
            "fixture_source": "real_fixture",
        },
        {
            "element": 999,  # Relegated player (e.g. historical season player)
            "name": "Wayne Rooney",
            "name_normalized": "wayne rooney",
            "predicted_total_points": 4.2,
            "predicted_for_gw": 2,
            "opponent_team": "Everton",
            "is_home": 0,
            "fixture_difficulty": 2,
            "fixture_source": "proxy_last_played",
        },
    ])


def test_current_fpl_player_pool_is_driven_by_bootstrap_elements(
    mock_bootstrap_static, mock_historical_model_predictions
):
    team_metadata = build_team_metadata(mock_bootstrap_static["teams"])
    player_metadata = build_player_metadata(mock_bootstrap_static["elements"])

    result_df = _build_current_fpl_prediction_pool(
        predictions=mock_historical_model_predictions,
        player_id_column="element",
        team_fixtures=None,
        team_metadata=team_metadata,
        player_metadata=player_metadata,
    )

    # 1. Verification: Exactly 2 current players from bootstrap elements
    assert len(result_df) == 2
    assert set(result_df["id"]) == {101, 202}

    # 2. Verification: Relegated player (#999) does NOT appear in current pool
    assert 999 not in result_df["id"].values

    # 3. Verification: Promoted team player (#202 - Delap) appears in current pool
    delap_row = result_df[result_df["id"] == 202].iloc[0]
    assert delap_row["name"] == "Delap"
    assert delap_row["team"] == "Ipswich Town"
    assert delap_row["predicted_total_points"] is None  # Unmatched prediction returns None

    # 4. Verification: Historical model prediction correctly merged for Saka (#101)
    saka_row = result_df[result_df["id"] == 101].iloc[0]
    assert saka_row["name"] == "Saka"
    assert saka_row["team"] == "Arsenal"
    assert saka_row["predicted_total_points"] == 6.8

