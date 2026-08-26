"""Unit tests for FeaturePipeline, the default-steps factory, and the summary writer."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.config.settings import FeatureEngineeringSettings
from src.feature_engineering.factory import build_default_feature_steps
from src.feature_engineering.models import FeatureStepSummary
from src.feature_engineering.pipeline import FeaturePipeline
from src.feature_engineering.steps.base import FeatureStep
from src.feature_engineering.summary_writer import write_summary


class _AddColumnStep(FeatureStep):
    @property
    def name(self) -> str:
        return "add_column"

    def apply(self, data: pd.DataFrame) -> tuple[pd.DataFrame, FeatureStepSummary]:
        result = data.copy()
        result["added"] = 1
        return result, FeatureStepSummary(
            step_name=self.name,
            rows_before=len(data),
            rows_after=len(result),
            columns_added=["added"],
            description="added a column",
        )


def test_pipeline_runs_steps_in_order_and_threads_data() -> None:
    """Each step's output must become the next step's input."""
    pipeline = FeaturePipeline(steps=[_AddColumnStep()])
    df = pd.DataFrame({"x": [1, 2, 3]})
    result = pipeline.run(df)

    assert result.rows_before == 3
    assert result.rows_after == 3
    assert "added" in result.data.columns
    assert len(result.step_summaries) == 1


def test_pipeline_never_removes_rows() -> None:
    """Feature engineering must never change the row count."""
    pipeline = FeaturePipeline(steps=[_AddColumnStep()])
    result = pipeline.run(pd.DataFrame({"x": [1, 2, 3, 4]}))
    assert result.rows_before == result.rows_after


def test_build_default_feature_steps_returns_ten_steps() -> None:
    """The factory must build the full standard step sequence, including fixture_difficulty."""
    steps = build_default_feature_steps(FeatureEngineeringSettings())
    names = [step.name for step in steps]
    assert names == [
        "rolling_averages",
        "player_participation",
        "promoted_and_historical",
        "fixture_difficulty",
        "home_away_flag",
        "rest_days",
        "team_opponent_strength",
        "team_form_trend",
        "price_trend",
        "form_index",
    ]


def test_default_pipeline_produces_expected_columns_on_realistic_data() -> None:
    """End-to-end: the default pipeline must add every requested Sprint 5 feature."""
    df = pd.DataFrame(
        {
            "element": [1, 1, 1],
            "season": ["2022-23"] * 3,
            "GW": [1, 2, 3],
            "total_points": [10, 8, 12],
            "minutes": [90, 90, 45],
            "bps": [20, 15, 25],
            "ict_index": [5.0, 4.0, 6.0],
            "expected_goals": [0.2, 0.1, 0.3],
            "expected_assists": [0.1, 0.2, 0.0],
            "was_home": [True, False, True],
            "kickoff_time": [
                "2022-08-06T14:00:00Z",
                "2022-08-13T14:00:00Z",
                "2022-08-20T14:00:00Z",
            ],
            "team": ["Arsenal", "Arsenal", "Arsenal"],
            "opponent_team": ["Chelsea", "Fulham", "Everton"],
            "team_h_score": [2, 1, 3],
            "team_a_score": [1, 0, 1],
            "value": [50, 51, 51],
        }
    )
    steps = build_default_feature_steps(FeatureEngineeringSettings())
    pipeline = FeaturePipeline(steps=steps)
    result = pipeline.run(df)
    engineered = result.data

    expected_columns = [
        "total_points_avg_last_3",
        "minutes_avg_last_5",
        "prev_gw_minutes",
        "prev_gw_played",
        "prev_gw_started",
        "prev_gw_bench_unused",
        "starts_last_3",
        "bench_unused_last_3",
        "is_promoted_team",
        "opponent_is_promoted_team",
        "player_is_new_to_pl",
        "prev_season_minutes",
        "prev_season_points",
        "prev_season_matches",
        "prev_season_ppm",
        "team_attack_strength",
        "team_defence_strength",
        "opponent_attack_strength",
        "opponent_defence_strength",
        "fixture_difficulty",
        "clean_sheet_likelihood",
        "bps_avg_last_10",
        "ict_index_avg_last_3",
        "xG_avg_last_3",
        "xA_avg_last_3",
        "is_home",
        "rest_days",
        "team_strength",
        "team_form_trend",
        "price_trend_last_1",
        "price_trend_last_5",
        "form_index",
    ]
    for column in expected_columns:
        assert column in engineered.columns, f"missing expected column: {column}"

    assert len(engineered) == 3
    # No leakage: first row's rolling average must be NaN (no prior match).
    assert pd.isna(engineered.iloc[0]["total_points_avg_last_3"])


def test_write_summary_produces_valid_json(tmp_path: Path) -> None:
    """write_summary must produce a JSON file describing the pipeline run."""
    pipeline = FeaturePipeline(steps=[_AddColumnStep()])
    result = pipeline.run(pd.DataFrame({"x": [1, 2, 3]}))

    summary_path = tmp_path / "summary.json"
    write_summary(result, summary_path)

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["rows_before"] == 3
    assert payload["rows_after"] == 3
    assert payload["steps"][0]["step_name"] == "add_column"
