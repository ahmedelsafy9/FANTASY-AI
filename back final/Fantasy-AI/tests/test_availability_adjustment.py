"""Unit tests for the availability adjustment post-processor."""

import pandas as pd
import pytest
from src.prediction.availability_adjustment import (
    adjust_predictions_for_availability,
    _compute_adjustment_factor,
)


def test_compute_adjustment_factor_fit():
    row = pd.Series({
        "availability_status": "fit",
        "availability_expected_minutes": 90.0,
        "chance_of_playing_next_round": 100,
    })
    assert _compute_adjustment_factor(row) == 1.0


def test_compute_adjustment_factor_major_injury():
    row = pd.Series({
        "availability_status": "major_injury",
        "availability_expected_minutes": 0.0,
        "chance_of_playing_next_round": 0,
    })
    assert _compute_adjustment_factor(row) == 0.0


def test_compute_adjustment_factor_suspended():
    row = pd.Series({
        "availability_status": "suspended",
        "availability_expected_minutes": 0.0,
    })
    assert _compute_adjustment_factor(row) == 0.0


def test_compute_adjustment_factor_doubtful():
    row_75 = pd.Series({
        "availability_status": "doubtful",
        "chance_of_playing_next_round": 75,
        "availability_expected_minutes": 67.5,
    })
    assert _compute_adjustment_factor(row_75) == 0.75

    row_50 = pd.Series({
        "availability_status": "doubtful",
        "chance_of_playing_next_round": 50,
        "availability_expected_minutes": 45.0,
    })
    assert _compute_adjustment_factor(row_50) == 0.50


def test_adjust_predictions_dataframe():
    df = pd.DataFrame([
        {
            "player_id": 1,
            "web_name": "Haaland",
            "predicted_expected_points": 7.5,
            "availability_status": "fit",
            "availability_expected_minutes": 90.0,
            "chance_of_playing_next_round": 100,
        },
        {
            "player_id": 2,
            "web_name": "Saka",
            "predicted_expected_points": 6.0,
            "availability_status": "doubtful",
            "availability_expected_minutes": 67.5,
            "chance_of_playing_next_round": 75,
        },
        {
            "player_id": 3,
            "web_name": "Saliba",
            "predicted_expected_points": 5.0,
            "availability_status": "major_injury",
            "availability_expected_minutes": 0.0,
            "chance_of_playing_next_round": 0,
        },
    ])

    adjusted = adjust_predictions_for_availability(df)

    # Raw points preserved
    assert "predicted_expected_points_raw" in adjusted.columns
    assert adjusted.loc[adjusted["player_id"] == 1, "predicted_expected_points_raw"].iloc[0] == 7.5
    assert adjusted.loc[adjusted["player_id"] == 2, "predicted_expected_points_raw"].iloc[0] == 6.0
    assert adjusted.loc[adjusted["player_id"] == 3, "predicted_expected_points_raw"].iloc[0] == 5.0

    # Adjusted points
    assert adjusted.loc[adjusted["player_id"] == 1, "predicted_expected_points"].iloc[0] == 7.5
    assert adjusted.loc[adjusted["player_id"] == 2, "predicted_expected_points"].iloc[0] == pytest.approx(4.5)
    assert adjusted.loc[adjusted["player_id"] == 3, "predicted_expected_points"].iloc[0] == 0.0

    # Adjustment factors
    assert adjusted.loc[adjusted["player_id"] == 1, "availability_adjustment_factor"].iloc[0] == 1.0
    assert adjusted.loc[adjusted["player_id"] == 2, "availability_adjustment_factor"].iloc[0] == 0.75
    assert adjusted.loc[adjusted["player_id"] == 3, "availability_adjustment_factor"].iloc[0] == 0.0
