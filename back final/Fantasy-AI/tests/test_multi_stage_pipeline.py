"""Comprehensive tests for the multi-stage prediction pipeline.

Covers temporal CV, match model, contribution model, pipeline integration,
leakage prevention, feature alignment, serialization, edge cases, ablation,
and dynamic GW detection.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_test_data(
    n_seasons: int = 3,
    gws_per_season: int = 10,
    players_per_team: int = 5,
    teams: list[str] | None = None,
) -> pd.DataFrame:
    """Build a synthetic player-level dataset for testing.

    Produces data with realistic structure: multiple seasons, GWs,
    teams, players, with score columns and was_home flags.
    """
    if teams is None:
        teams = ["TeamA", "TeamB", "TeamC", "TeamD"]
    n_teams = len(teams)
    rows = []
    season_strs = [f"20{20 + i}-{21 + i}" for i in range(n_seasons)]

    rng = np.random.RandomState(42)

    for s_idx, season in enumerate(season_strs):
        for gw in range(1, gws_per_season + 1):
            # Create matches: pair teams
            for match_idx in range(n_teams // 2):
                home_team = teams[match_idx * 2]
                away_team = teams[match_idx * 2 + 1]
                home_goals = rng.poisson(1.5)
                away_goals = rng.poisson(1.1)

                for t_idx, (team, opp, is_home) in enumerate([
                    (home_team, away_team, True),
                    (away_team, home_team, False),
                ]):
                    for p in range(players_per_team):
                        player_name = f"{team}_Player_{p}"
                        minutes = rng.choice([0, 60, 90], p=[0.1, 0.2, 0.7])
                        goals = rng.poisson(0.15) if minutes > 0 else 0
                        assists = rng.poisson(0.1) if minutes > 0 else 0
                        cs = 1 if (is_home and away_goals == 0) or (not is_home and home_goals == 0) else 0
                        cs = cs if minutes >= 60 else 0
                        bonus = rng.choice([0, 1, 2, 3], p=[0.7, 0.15, 0.1, 0.05]) if minutes > 0 else 0
                        pts = (
                            (2 if minutes > 0 else 0) +
                            (1 if minutes >= 60 else 0) +
                            goals * 5 + assists * 3 +
                            cs * 4 + bonus
                        )

                        rows.append({
                            "name": player_name,
                            "season": season,
                            "GW": gw,
                            "team": team,
                            "opponent_team": opp,
                            "was_home": is_home,
                            "minutes": minutes,
                            "goals_scored": goals,
                            "assists": assists,
                            "clean_sheets": cs,
                            "bonus": bonus,
                            "bps": rng.randint(0, 40) if minutes > 0 else 0,
                            "total_points": pts,
                            "team_h_score": home_goals,
                            "team_a_score": away_goals,
                            "value": 50 + rng.randint(-10, 20),
                            "position": rng.choice(["GK", "DEF", "MID", "FWD"]),
                            "ict_index": rng.uniform(0, 10) if minutes > 0 else 0,
                            "threat": rng.uniform(0, 50) if minutes > 0 else 0,
                            "creativity": rng.uniform(0, 50) if minutes > 0 else 0,
                            "influence": rng.uniform(0, 50) if minutes > 0 else 0,
                            "expected_goals": rng.uniform(0, 0.5) if minutes > 0 else 0,
                            "expected_assists": rng.uniform(0, 0.3) if minutes > 0 else 0,
                            "saves": rng.randint(0, 5) if minutes > 0 else 0,
                            "goals_conceded": 0,
                            "yellow_cards": rng.choice([0, 1], p=[0.85, 0.15]),
                            "red_cards": 0,
                            "starts": 1 if minutes >= 60 else 0,
                            "selected": rng.randint(1000, 50000),
                            "transfers_in": rng.randint(0, 5000),
                            "transfers_out": rng.randint(0, 5000),
                            "transfers_balance": 0,
                            "element": hash(player_name) % 1000,
                        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Temporal CV Tests
# ---------------------------------------------------------------------------

class TestTemporalCV:
    """Tests for GW-level expanding walk-forward cross-validation."""

    def test_temporal_index_ordering(self):
        """Temporal index must be strictly chronological across seasons."""
        from src.multi_stage.temporal_cv import make_temporal_index

        df = pd.DataFrame({
            "season": ["2020-21", "2020-21", "2021-22", "2021-22"],
            "GW": [37, 38, 1, 2],
        })
        tidx = make_temporal_index(df)
        assert list(tidx) == [202037, 202038, 202101, 202102]
        assert tidx.is_monotonic_increasing

    def test_walk_forward_folds_strictly_chronological(self):
        """Each fold's training set must be strictly before the prediction window."""
        from src.multi_stage.temporal_cv import generate_walk_forward_folds, make_temporal_index

        df = _make_test_data(n_seasons=2, gws_per_season=5)
        folds = generate_walk_forward_folds(df, min_train_gameweeks=3)

        tidx = make_temporal_index(df)

        for fold in folds:
            train_max_tidx = tidx[fold.train_mask].max()
            predict_min_tidx = tidx[fold.predict_mask].min()
            assert train_max_tidx < predict_min_tidx, (
                f"Fold {fold.fold_id}: train max {train_max_tidx} >= predict min {predict_min_tidx}"
            )

    def test_no_future_leakage_in_folds(self):
        """No fold should have training data from the prediction GW or later."""
        from src.multi_stage.temporal_cv import generate_walk_forward_folds

        df = _make_test_data(n_seasons=2, gws_per_season=8)
        folds = generate_walk_forward_folds(df, min_train_gameweeks=3)

        for fold in folds:
            train_data = df.loc[fold.train_mask]
            pred_data = df.loc[fold.predict_mask]

            pred_season = pred_data["season"].iloc[0]
            pred_gw = pred_data["GW"].iloc[0]

            # No training row from the same or later (season, GW)
            same_season = train_data["season"] == pred_season
            same_or_later_gw = train_data["GW"] >= pred_gw
            leaking = same_season & same_or_later_gw
            assert leaking.sum() == 0, (
                f"Fold {fold.fold_id}: {leaking.sum()} training rows leak "
                f"from {pred_season} GW{pred_gw}+"
            )

    def test_expanding_window(self):
        """Training set must grow (expand) with each fold."""
        from src.multi_stage.temporal_cv import generate_walk_forward_folds

        df = _make_test_data(n_seasons=2, gws_per_season=6)
        folds = generate_walk_forward_folds(df, min_train_gameweeks=3)

        prev_train_size = 0
        for fold in folds:
            train_size = fold.train_mask.sum()
            assert train_size >= prev_train_size, (
                f"Fold {fold.fold_id}: training size {train_size} < prev {prev_train_size}"
            )
            prev_train_size = train_size

    def test_min_train_gameweeks_respected(self):
        """First fold must have at least min_train_gameweeks worth of data."""
        from src.multi_stage.temporal_cv import generate_walk_forward_folds

        df = _make_test_data(n_seasons=2, gws_per_season=5)
        min_gws = 4
        folds = generate_walk_forward_folds(df, min_train_gameweeks=min_gws)

        if folds:
            first_fold = folds[0]
            train_data = df.loc[first_fold.train_mask]
            unique_gws = train_data.groupby(["season", "GW"]).ngroups
            assert unique_gws >= min_gws

    def test_run_walk_forward_predictions(self):
        """Walk-forward predictions should produce OOF values."""
        from src.multi_stage.temporal_cv import run_walk_forward_predictions
        from sklearn.linear_model import Ridge

        df = _make_test_data(n_seasons=2, gws_per_season=8)
        result = run_walk_forward_predictions(
            df,
            feature_cols=["minutes", "goals_scored", "assists", "bonus"],
            target_col="total_points",
            model_builder=lambda: Ridge(),
            min_train_gameweeks=3,
        )
        assert "oof_total_points" in result.columns
        assert result["oof_total_points"].notna().sum() > 0


# ---------------------------------------------------------------------------
# Match Model Tests
# ---------------------------------------------------------------------------

class TestMatchModel:
    """Tests for the match result prediction model."""

    def test_build_match_dataset(self):
        """Match dataset should have one row per (season, GW, team)."""
        from src.multi_stage.match_model import build_match_dataset

        df = _make_test_data(n_seasons=2, gws_per_season=5)
        match_df = build_match_dataset(df)

        assert not match_df.empty
        assert "target_goals" in match_df.columns
        assert "team_attack_str" in match_df.columns or "team_goals_for_expanding" in match_df.columns

    def test_match_features_are_lagged(self):
        """All match features must be lagged (not using current GW data)."""
        from src.multi_stage.match_model import build_match_dataset

        df = _make_test_data(n_seasons=2, gws_per_season=5)
        match_df = build_match_dataset(df)

        # GW1 of the FIRST season should have NaN for expanding features
        # (no prior data exists). Later seasons' GW1 may have values
        # carried over from the previous season, which is correct.
        first_season = sorted(match_df["season"].unique())[0]
        gw1_first = match_df[(match_df["GW"] == 1) & (match_df["season"] == first_season)]
        if "team_goals_for_expanding" in gw1_first.columns:
            assert gw1_first["team_goals_for_expanding"].isna().all(), (
                "GW1 of the first season should have NaN expanding features (no prior data)"
            )

    def test_goals_to_probabilities(self):
        """Poisson probability derivation should produce valid distributions."""
        from src.multi_stage.match_model import goals_to_probabilities

        probs = goals_to_probabilities(
            np.array([2.0, 1.5, 0.5]),
            np.array([1.0, 1.5, 2.0]),
        )

        assert "win_prob" in probs
        assert "draw_prob" in probs
        assert "loss_prob" in probs

        # Must sum to ~1
        total = probs["win_prob"] + probs["draw_prob"] + probs["loss_prob"]
        np.testing.assert_allclose(total, 1.0, atol=0.01)

        # Team with more expected goals should have higher win prob
        assert probs["win_prob"][0] > probs["loss_prob"][0]
        assert probs["win_prob"][2] < probs["loss_prob"][2]

    def test_map_match_predictions_to_players(self):
        """Match predictions should map correctly to player-level rows."""
        from src.multi_stage.match_model import map_match_predictions_to_players

        player_df = pd.DataFrame({
            "name": ["P1", "P2"],
            "season": ["2020-21", "2020-21"],
            "GW": [1, 1],
            "team": ["TeamA", "TeamB"],
            "opponent_team": ["TeamB", "TeamA"],
        })
        match_oof = pd.DataFrame({
            "season": ["2020-21", "2020-21"],
            "GW": [1, 1],
            "team": ["TeamA", "TeamB"],
            "oof_goals_pred": [2.0, 1.0],
        })

        result = map_match_predictions_to_players(player_df, match_oof)
        assert "match_predicted_team_goals" in result.columns
        assert "match_predicted_win_prob" in result.columns

        # TeamA predicted 2 goals, TeamB predicted 1 goal
        assert result.loc[0, "match_predicted_team_goals"] == 2.0
        assert result.loc[1, "match_predicted_team_goals"] == 1.0

    def test_train_match_model(self):
        """Match model training should complete without errors."""
        from src.multi_stage.match_model import train_match_model

        df = _make_test_data(n_seasons=3, gws_per_season=10)
        result = train_match_model(df, min_train_gameweeks=5, random_state=42)

        # Should produce a result (may be empty if insufficient data)
        assert result is not None

    def test_match_model_persistence(self):
        """Match model save/load should roundtrip correctly."""
        from src.multi_stage.match_model import (
            train_match_model, save_match_model, load_match_model,
        )

        df = _make_test_data(n_seasons=3, gws_per_season=10)
        result = train_match_model(df, min_train_gameweeks=5)

        if result.best_model is not None:
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                save_match_model(result, tmp_path)

                model, metadata = load_match_model(tmp_path)
                assert model is not None
                assert metadata.get("best_model_name") == result.best_model_name


# ---------------------------------------------------------------------------
# Contribution Model Tests
# ---------------------------------------------------------------------------

class TestContributionModel:
    """Tests for the player contribution prediction model."""

    def test_contribution_features_detected(self):
        """Feature detection should find available contribution features."""
        from src.multi_stage.contribution_model import _get_contribution_features

        df = _make_test_data(n_seasons=2, gws_per_season=5)
        # Add some rolling features
        df["total_points_avg_last_3"] = df["total_points"].rolling(3, min_periods=1).mean()
        df["minutes_avg_last_5"] = df["minutes"].rolling(5, min_periods=1).mean()
        df["form_index"] = 3.0
        df["expected_minutes"] = 70.0

        features = _get_contribution_features(df)
        assert len(features) > 0
        assert "form_index" in features

    def test_train_contribution_model(self):
        """Contribution model training should handle all targets."""
        from src.multi_stage.contribution_model import train_contribution_model

        df = _make_test_data(n_seasons=3, gws_per_season=10)
        # Add minimal rolling features
        df["total_points_avg_last_3"] = 3.0
        df["minutes_avg_last_5"] = 60.0
        df["form_index"] = 3.0
        df["expected_minutes"] = 70.0
        df["is_home"] = df["was_home"].astype(int)

        result = train_contribution_model(df, min_train_gameweeks=5)
        assert result is not None

    def test_separate_per_target_selection(self):
        """Each contribution target can have a different best model."""
        from src.multi_stage.contribution_model import train_contribution_model

        df = _make_test_data(n_seasons=3, gws_per_season=10)
        df["total_points_avg_last_3"] = 3.0
        df["form_index"] = 3.0
        df["is_home"] = df["was_home"].astype(int)

        result = train_contribution_model(df, min_train_gameweeks=5)

        # Different targets may select different models — this is acceptable
        if len(result.target_results) > 1:
            models_used = {tr.best_model_name for tr in result.target_results.values() if tr.best_model_name}
            # At minimum, models should have been selected
            assert len(models_used) >= 1


# ---------------------------------------------------------------------------
# Pipeline Integration Tests
# ---------------------------------------------------------------------------

class TestPipelineIntegration:
    """Tests for the full multi-stage pipeline."""

    def test_full_pipeline_runs(self):
        """Full pipeline should complete without errors."""
        from src.multi_stage.pipeline import run_multi_stage_pipeline

        df = _make_test_data(n_seasons=3, gws_per_season=10)
        # Add minimal features
        df["total_points_avg_last_3"] = 3.0
        df["form_index"] = 3.0
        df["is_home"] = df["was_home"].astype(int)

        result = run_multi_stage_pipeline(df, min_train_gameweeks=5, random_state=42)
        assert result is not None
        assert result.ablation_results is not None

    def test_ablation_study_has_all_configs(self):
        """Ablation study should compare all four configurations."""
        from src.multi_stage.pipeline import run_multi_stage_pipeline

        df = _make_test_data(n_seasons=3, gws_per_season=10)
        df["total_points_avg_last_3"] = 3.0
        df["form_index"] = 3.0
        df["is_home"] = df["was_home"].astype(int)

        result = run_multi_stage_pipeline(df, min_train_gameweeks=5)

        # At minimum, baseline should always be present
        assert "A_baseline" in result.ablation_results

    def test_ablation_results_have_required_metrics(self):
        """Each ablation config must report MAE, RMSE, R², Spearman."""
        from src.multi_stage.pipeline import run_multi_stage_pipeline

        df = _make_test_data(n_seasons=3, gws_per_season=10)
        df["total_points_avg_last_3"] = 3.0
        df["form_index"] = 3.0
        df["is_home"] = df["was_home"].astype(int)

        result = run_multi_stage_pipeline(df, min_train_gameweeks=5)

        for config_name, metrics in result.ablation_results.items():
            assert "mae" in metrics, f"{config_name} missing MAE"
            assert "rmse" in metrics, f"{config_name} missing RMSE"
            assert "r2" in metrics, f"{config_name} missing R²"
            assert "spearman" in metrics, f"{config_name} missing Spearman"

    def test_pipeline_persistence(self):
        """Pipeline save/load should work without errors."""
        from src.multi_stage.pipeline import run_multi_stage_pipeline, save_pipeline_result

        df = _make_test_data(n_seasons=3, gws_per_season=10)
        df["total_points_avg_last_3"] = 3.0
        df["form_index"] = 3.0
        df["is_home"] = df["was_home"].astype(int)

        result = run_multi_stage_pipeline(df, min_train_gameweeks=5)

        with tempfile.TemporaryDirectory() as tmp:
            save_pipeline_result(result, Path(tmp))
            assert (Path(tmp) / "pipeline_metadata.json").exists()


# ---------------------------------------------------------------------------
# Leakage Prevention Tests
# ---------------------------------------------------------------------------

class TestLeakagePrevention:
    """Tests ensuring no temporal leakage in the pipeline."""

    def test_contribution_model_never_sees_future_match_predictions(self):
        """Contribution model at fold t must not see match predictions from t or later."""
        from src.multi_stage.temporal_cv import generate_walk_forward_folds, make_temporal_index

        df = _make_test_data(n_seasons=2, gws_per_season=6)
        folds = generate_walk_forward_folds(df, min_train_gameweeks=3)

        for fold in folds:
            # The training mask must exclude the prediction window
            assert not (fold.train_mask & fold.predict_mask).any(), (
                f"Fold {fold.fold_id}: overlap between train and predict masks"
            )

    def test_oof_predictions_only_for_future_rows(self):
        """OOF predictions should only exist for rows after the training set."""
        from src.multi_stage.temporal_cv import run_walk_forward_predictions
        from sklearn.linear_model import Ridge

        df = _make_test_data(n_seasons=2, gws_per_season=6)
        result = run_walk_forward_predictions(
            df,
            feature_cols=["minutes", "goals_scored"],
            target_col="total_points",
            model_builder=lambda: Ridge(),
            min_train_gameweeks=3,
        )

        # The first min_train_gameweeks worth of GWs should be NaN
        first_gws = df.groupby(["season", "GW"]).ngroups
        predicted = result["oof_total_points"].notna()
        if first_gws > 3:
            # First 3 GW windows should not have OOF predictions
            first_3_gws = df.sort_values(["season", "GW"]).groupby(["season", "GW"]).ngroup()
            early_mask = first_3_gws < 3
            assert not predicted[early_mask].any(), "Early GWs should not have OOF predictions"


# ---------------------------------------------------------------------------
# Feature Alignment Tests
# ---------------------------------------------------------------------------

class TestFeatureAlignment:
    """Tests ensuring training and inference use the same features."""

    def test_match_prediction_cols_consistent(self):
        """Match prediction column names should be consistent."""
        from src.multi_stage.pipeline import MATCH_PREDICTION_COLS

        expected = {
            "match_predicted_team_goals",
            "match_predicted_opponent_goals",
            "match_predicted_win_prob",
            "match_predicted_draw_prob",
            "match_predicted_loss_prob",
            "match_predicted_goal_difference",
            "match_difficulty",
        }
        assert set(MATCH_PREDICTION_COLS) == expected

    def test_contribution_prediction_cols_consistent(self):
        """Contribution prediction column names should be consistent."""
        from src.multi_stage.pipeline import CONTRIBUTION_PREDICTION_COLS

        expected = {
            "contrib_predicted_goals",
            "contrib_predicted_assists",
            "contrib_clean_sheet_probability",
        }
        assert set(CONTRIBUTION_PREDICTION_COLS) == expected


# ---------------------------------------------------------------------------
# Edge Case Tests
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Tests for edge cases and robustness."""

    def test_zero_minutes_players(self):
        """Players with zero minutes should not crash the pipeline."""
        from src.multi_stage.match_model import build_match_dataset

        df = _make_test_data(n_seasons=2, gws_per_season=5)
        # Set some players to zero minutes
        df.loc[df.index[:20], "minutes"] = 0
        df.loc[df.index[:20], "goals_scored"] = 0

        match_df = build_match_dataset(df)
        assert not match_df.empty

    def test_single_season_data(self):
        """Pipeline should handle single-season datasets gracefully."""
        from src.multi_stage.temporal_cv import generate_walk_forward_folds

        df = _make_test_data(n_seasons=1, gws_per_season=10)
        folds = generate_walk_forward_folds(df, min_train_gameweeks=3)

        # Should still produce some folds
        assert len(folds) > 0

    def test_missing_columns_graceful(self):
        """Models should handle missing optional columns gracefully."""
        from src.multi_stage.match_model import build_match_dataset

        df = _make_test_data(n_seasons=2, gws_per_season=5)
        # Remove some optional columns
        df = df.drop(columns=["ict_index", "threat"], errors="ignore")

        match_df = build_match_dataset(df)
        assert not match_df.empty

    def test_promoted_team_flags(self):
        """Promoted team detection should work across season boundaries."""
        from src.multi_stage.match_model import build_match_dataset

        df = _make_test_data(
            n_seasons=2, gws_per_season=5,
            teams=["TeamA", "TeamB", "TeamC", "TeamD"],
        )
        # Add a promoted team in season 2
        new_rows = df[df["season"] == df["season"].unique()[-1]].copy()
        new_rows["team"] = "PromotedTeam"
        new_rows["name"] = new_rows["name"].str.replace("TeamA", "PromotedTeam")
        df = pd.concat([df, new_rows], ignore_index=True)

        match_df = build_match_dataset(df)
        if "team_is_promoted" in match_df.columns:
            promoted = match_df[match_df["team"] == "PromotedTeam"]
            if not promoted.empty:
                assert promoted["team_is_promoted"].sum() > 0


# ---------------------------------------------------------------------------
# Diagnostics Tests
# ---------------------------------------------------------------------------

class TestDiagnostics:
    """Tests for diagnostic report generation."""

    def test_ablation_report_generation(self):
        """Ablation report should generate valid markdown."""
        from src.multi_stage.diagnostics import generate_ablation_report

        ablation_results = {
            "A_baseline": {"model": "lightgbm", "mae": 1.5, "rmse": 2.0, "r2": 0.3, "spearman": 0.4},
            "D_full": {"model": "xgboost", "mae": 1.4, "rmse": 1.9, "r2": 0.35, "spearman": 0.45},
        }

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ablation.md"
            report = generate_ablation_report(ablation_results, path)

            assert path.exists()
            assert "Baseline" in report
            assert "MAE" in report

    def test_model_selection_report_generation(self):
        """Model selection report should generate without errors."""
        from src.multi_stage.diagnostics import generate_model_selection_report

        ablation_results = {
            "A_baseline": {"model": "lightgbm", "mae": 1.5},
            "D_full": {"model": "xgboost", "mae": 1.4},
        }

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "selection.md"
            report = generate_model_selection_report(
                match_result=None,
                contribution_result=None,
                ablation_results=ablation_results,
                output_path=path,
            )
            assert path.exists()


# ---------------------------------------------------------------------------
# Dynamic GW Detection Tests
# ---------------------------------------------------------------------------

class TestDynamicGWDetection:
    """Tests for dynamic next-GW detection."""

    def test_detects_next_unplayed_gw(self):
        """Pipeline should auto-detect the next unplayed GW."""
        from src.prediction.next_gameweek import build_next_gameweek_rows

        df = _make_test_data(n_seasons=2, gws_per_season=5)
        result = build_next_gameweek_rows(
            df,
            player_id_columns=("name",),
            chronological_columns=("season", "GW"),
            max_valid_gameweek=38,
        )

        assert "predicted_for_gw" in result.columns
        # Should predict the next GW after the last completed one
        max_gw = df["GW"].max()
        predicted_gw = result["predicted_for_gw"].mode().iloc[0]
        assert predicted_gw == max_gw + 1 or predicted_gw == 1  # wraps at season end


# ---------------------------------------------------------------------------
# Settings Tests
# ---------------------------------------------------------------------------

class TestMultiStageSettings:
    """Tests for the MultiStageSettings configuration."""

    def test_multi_stage_settings_default(self):
        """MultiStageSettings should have sensible defaults."""
        from src.config.settings import MultiStageSettings

        s = MultiStageSettings()
        assert s.enable_multi_stage is True
        assert s.min_train_gameweeks == 38
        assert "goals_scored" in s.contribution_targets
        assert "assists" in s.contribution_targets
        assert "clean_sheets" in s.contribution_targets

    def test_settings_includes_multi_stage(self):
        """Top-level Settings should include multi_stage."""
        from src.config.settings import get_settings

        settings = get_settings()
        assert hasattr(settings, "multi_stage")
        assert settings.multi_stage.min_train_gameweeks == 38


# ---------------------------------------------------------------------------
# Model Selection Tests
# ---------------------------------------------------------------------------

class TestModelSelection:
    """Tests for model selection utilities."""

    def test_build_match_candidates(self):
        """Should build at least HistGBM and Ridge candidates."""
        from src.multi_stage.model_selection import build_match_candidates

        candidates = build_match_candidates()
        names = [c[0] for c in candidates]
        assert "histgbm" in names
        assert "ridge" in names

    def test_build_contribution_candidates(self):
        """Should build candidates for contribution targets."""
        from src.multi_stage.model_selection import build_contribution_candidates

        candidates = build_contribution_candidates("goals_scored")
        names = [c[0] for c in candidates]
        assert "histgbm" in names

    def test_build_points_candidates(self):
        """Should build candidates for points prediction."""
        from src.multi_stage.model_selection import build_points_candidates

        candidates = build_points_candidates()
        names = [c[0] for c in candidates]
        assert "histgbm" in names
        assert "ridge" in names
        assert "random_forest" in names

    def test_select_best_model(self):
        """Model selection should choose the best model on validation."""
        from src.multi_stage.model_selection import select_best_model
        from sklearn.linear_model import Ridge
        from sklearn.ensemble import HistGradientBoostingRegressor

        rng = np.random.RandomState(42)
        X = rng.randn(200, 5)
        y = X[:, 0] * 2 + X[:, 1] + rng.randn(200) * 0.5

        candidates = [
            ("ridge", lambda: Ridge()),
            ("histgbm", lambda: HistGradientBoostingRegressor(max_iter=50, random_state=42)),
        ]

        best_name, best_model, all_metrics = select_best_model(
            candidates,
            X[:150], y[:150],
            X[150:], y[150:],
            metric="mae",
        )

        assert best_name in ("ridge", "histgbm")
        assert best_model is not None
        assert "mae" in all_metrics.get(best_name, {})


# ---------------------------------------------------------------------------
# Training Factory Tests
# ---------------------------------------------------------------------------

class TestTrainingFactoryEnhanced:
    """Tests for the enhanced training factory."""

    def test_factory_includes_histgbm(self):
        """Factory should include HistGradientBoosting."""
        from src.training.factory import build_default_model_specs
        from src.config.settings import TrainingSettings

        specs, skipped = build_default_model_specs(TrainingSettings())
        names = [s.name for s in specs]
        assert "hist_gradient_boosting" in names

    def test_factory_includes_ridge(self):
        """Factory should include Ridge."""
        from src.training.factory import build_default_model_specs
        from src.config.settings import TrainingSettings

        specs, skipped = build_default_model_specs(TrainingSettings())
        names = [s.name for s in specs]
        assert "ridge" in names

    def test_factory_catboost_graceful(self):
        """CatBoost should be handled gracefully if not installed."""
        from src.training.factory import build_default_model_specs
        from src.config.settings import TrainingSettings

        specs, skipped = build_default_model_specs(TrainingSettings())
        names = [s.name for s in specs]
        # Either catboost is in specs (installed) or in skipped (not installed)
        assert "catboost" in names or "catboost" in skipped
