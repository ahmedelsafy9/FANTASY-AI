"""Comprehensive tests for the production pipeline robustness:
composite scoring, promotion logic, idempotency, dry-run, and leakage checks.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from src.automation.update_pipeline import AutomationOrchestrator
from src.config.settings import Settings
from src.training.promotion_scorer import (
    CompositeModelScore,
    FPLMetrics,
    compute_composite_score,
    compute_fpl_metrics,
    select_best_model_fpl,
)


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------


def _build_vaastav_zip(n_gws: int = 10, season: str = "2022-23") -> bytes:
    rows = [
        "name,GW,element,total_points,minutes,bonus,bps,ict_index,"
        "was_home,value,team,opponent_team,kickoff_time"
    ]
    teams = ["Arsenal", "Chelsea"]
    for gw in range(1, n_gws + 1):
        for element, name in ((1, "Player One"), (2, "Player Two")):
            pts = 5 + gw % 3 + (element * 2)
            rows.append(
                f"{name},{gw},{element},{pts},90,1,20,5.0,True,50,"
                f"{teams[element % 2]},{teams[(element + 1) % 2]},"
                f"2022-08-{gw:02d}T14:00:00Z"
            )
    csv_text = "\n".join(rows) + "\n"

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(
            f"Fantasy-Premier-League-master/data/{season}/gws/merged_gw.csv",
            csv_text,
        )
    return buffer.getvalue()


def _bootstrap_payload(finished_events: list[int]) -> dict[str, Any]:
    events = [
        {
            "id": i,
            "finished": i in finished_events,
            "deadline_time": "2022-09-16T10:00:00Z",
        }
        for i in range(1, 15)
    ]
    return {
        "events": events,
        "teams": [
            {"id": 11, "name": "Arsenal"},
            {"id": 12, "name": "Chelsea"},
        ],
        "elements": [
            {"id": 1, "web_name": "Player One", "team": 11, "now_cost": 55},
            {"id": 2, "web_name": "Player Two", "team": 12, "now_cost": 60},
        ],
    }


def _live_payload(gw: int) -> dict[str, Any]:
    return {
        "elements": [
            {
                "id": 1,
                "stats": {
                    "minutes": 90,
                    "goals_scored": 1,
                    "total_points": 12,
                },
            },
            {
                "id": 2,
                "stats": {
                    "minutes": 90,
                    "goals_scored": 0,
                    "total_points": 4,
                },
            },
        ]
    }


class _FakeHttpResponse:
    def __init__(
        self, content: Any, status_code: int = 200, is_json: bool = False
    ) -> None:
        self._content = content
        self.status_code = status_code
        self._is_json = is_json

    def json(self) -> Any:
        return self._content

    def iter_content(self, chunk_size: int):
        yield self._content

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return None


@pytest.fixture
def isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Build Settings rooted at an isolated tmp_path."""
    monkeypatch.setenv("FANTASY_AI_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FANTASY_AI_MODELS_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("FANTASY_AI_CONFIGS_DIR", str(tmp_path / "configs"))
    monkeypatch.setenv("FANTASY_AI_LOGS_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("FANTASY_AI_ROLLING_WINDOWS", "3")
    monkeypatch.setenv("FANTASY_AI_TEST_FRACTION", "0.3")
    monkeypatch.setenv("FANTASY_AI_RF_N_ESTIMATORS", "10")
    monkeypatch.setenv("FANTASY_AI_BOOSTED_N_ESTIMATORS", "10")
    # Use composite promotion strategy
    monkeypatch.setenv("FANTASY_AI_PROMOTION_STRATEGY", "composite")
    return Settings()


def _patch_network(
    monkeypatch: pytest.MonkeyPatch,
    zip_bytes: bytes | None = None,
    bootstrap: dict | None = None,
    live: dict | None = None,
) -> None:
    def fake_get(url: str, stream: bool = False, timeout: int = 30):
        if "codeload.github.com" in url:
            if zip_bytes is None:
                raise AssertionError(f"Vaastav download should not have been called: {url}")
            return _FakeHttpResponse(zip_bytes)
        if "bootstrap-static" in url:
            if bootstrap is None:
                raise AssertionError(f"FPL API should not have been called: {url}")
            return _FakeHttpResponse(bootstrap)
        if "/event/" in url and "/live" in url:
            if live is None:
                raise AssertionError(f"FPL API should not have been called: {url}")
            return _FakeHttpResponse(live)
        raise AssertionError(f"Unexpected URL requested: {url}")

    monkeypatch.setattr("requests.get", fake_get)


# -----------------------------------------------------------------------
# Unit Tests: FPLMetrics and Composite Scoring
# -----------------------------------------------------------------------


class TestFPLMetrics:
    """Tests for FPL metric computation."""

    def test_compute_fpl_metrics_basic(self) -> None:
        y_true = np.array([1.0, 2.0, 3.0, 7.0, 10.0, 15.0])
        y_pred = np.array([1.5, 2.5, 2.5, 6.5, 9.0, 13.0])

        metrics = compute_fpl_metrics(y_true, y_pred)

        assert metrics.rmse > 0
        assert metrics.mae > 0
        assert metrics.r2 > 0
        assert -1.0 <= metrics.spearman_rho <= 1.0
        assert 0.0 <= metrics.recall_6 <= 1.0
        assert 0.0 <= metrics.recall_10 <= 1.0
        assert 0.0 <= metrics.precision_6 <= 1.0

    def test_compute_fpl_metrics_perfect_predictions(self) -> None:
        y_true = np.array([1.0, 3.0, 7.0, 12.0])
        y_pred = np.array([1.0, 3.0, 7.0, 12.0])

        metrics = compute_fpl_metrics(y_true, y_pred)

        assert metrics.rmse == pytest.approx(0.0, abs=1e-6)
        assert metrics.mae == pytest.approx(0.0, abs=1e-6)
        assert metrics.r2 == pytest.approx(1.0, abs=1e-6)
        assert metrics.spearman_rho == pytest.approx(1.0, abs=1e-6)
        assert metrics.recall_6 == pytest.approx(1.0)
        assert metrics.recall_10 == pytest.approx(1.0)

    def test_compute_fpl_metrics_zero_recall_when_under_predicted(self) -> None:
        y_true = np.array([1.0, 2.0, 8.0, 12.0])
        y_pred = np.array([1.0, 2.0, 3.0, 4.0])  # All under-predicted

        metrics = compute_fpl_metrics(y_true, y_pred)

        assert metrics.recall_6 == 0.0
        assert metrics.recall_10 == 0.0

    def test_fpl_metrics_to_dict(self) -> None:
        metrics = FPLMetrics(
            rmse=1.5, mae=0.8, r2=0.5,
            spearman_rho=0.7, recall_6=0.3,
            recall_10=0.1, precision_6=0.4, top_20_recall=0.5,
        )
        d = metrics.to_dict()
        assert d["rmse"] == 1.5
        assert d["spearman_rho"] == 0.7
        assert len(d) == 8


class TestCompositeScoring:
    """Tests for composite model scoring."""

    def test_single_candidate_gets_score_of_half(self) -> None:
        """With a single candidate, all normalized values are 0.5."""
        metrics = FPLMetrics(
            rmse=1.5, mae=0.8, r2=0.5,
            spearman_rho=0.7, recall_6=0.3,
            recall_10=0.1, precision_6=0.4, top_20_recall=0.5,
        )
        score = compute_composite_score(
            model_name="test",
            metrics=metrics,
            all_candidate_metrics=[metrics],
        )
        assert score.composite_score == pytest.approx(0.5, abs=0.01)
        assert score.eligible is True

    def test_two_candidates_better_model_wins(self) -> None:
        good = FPLMetrics(
            rmse=1.0, mae=0.5, r2=0.8,
            spearman_rho=0.9, recall_6=0.5,
            recall_10=0.3, precision_6=0.6, top_20_recall=0.7,
        )
        bad = FPLMetrics(
            rmse=3.0, mae=1.5, r2=0.2,
            spearman_rho=0.3, recall_6=0.1,
            recall_10=0.01, precision_6=0.1, top_20_recall=0.2,
        )
        all_metrics = [good, bad]

        good_score = compute_composite_score("good", good, all_metrics)
        bad_score = compute_composite_score("bad", bad, all_metrics)

        assert good_score.composite_score > bad_score.composite_score

    def test_gate_failure_makes_ineligible(self) -> None:
        metrics = FPLMetrics(
            rmse=5.0, mae=3.0, r2=0.1,  # rmse > 3.0 gate
            spearman_rho=0.3, recall_6=0.01,  # recall_6 < 0.05 gate
            recall_10=0.0, precision_6=0.1, top_20_recall=0.2,
        )
        score = compute_composite_score(
            model_name="bad",
            metrics=metrics,
            all_candidate_metrics=[metrics],
        )
        assert score.eligible is False
        assert len(score.gate_failures) == 2

    def test_gate_passing(self) -> None:
        metrics = FPLMetrics(
            rmse=1.5, mae=0.8, r2=0.5,
            spearman_rho=0.7, recall_6=0.3,
            recall_10=0.1, precision_6=0.4, top_20_recall=0.5,
        )
        score = compute_composite_score(
            model_name="good",
            metrics=metrics,
            all_candidate_metrics=[metrics],
        )
        assert score.eligible is True
        assert len(score.gate_failures) == 0

    def test_custom_weights(self) -> None:
        """Custom weights should shift the composite score."""
        metrics_a = FPLMetrics(
            rmse=2.0, mae=1.5, r2=0.3,
            spearman_rho=0.3, recall_6=0.8,
            recall_10=0.5, precision_6=0.7, top_20_recall=0.6,
        )
        metrics_b = FPLMetrics(
            rmse=1.0, mae=0.5, r2=0.7,
            spearman_rho=0.9, recall_6=0.1,
            recall_10=0.01, precision_6=0.1, top_20_recall=0.2,
        )
        all_m = [metrics_a, metrics_b]

        # With recall-heavy weights, model A should win
        recall_weights = {"recall_6": 0.8, "recall_10": 0.2}
        score_a = compute_composite_score("a", metrics_a, all_m, weights=recall_weights)
        score_b = compute_composite_score("b", metrics_b, all_m, weights=recall_weights)
        assert score_a.composite_score > score_b.composite_score

        # With accuracy-heavy weights, model B should win
        accuracy_weights = {"rmse": 0.5, "mae": 0.3, "spearman_rho": 0.2}
        score_a2 = compute_composite_score("a", metrics_a, all_m, weights=accuracy_weights)
        score_b2 = compute_composite_score("b", metrics_b, all_m, weights=accuracy_weights)
        assert score_b2.composite_score > score_a2.composite_score


class TestSelectBestModelFPL:
    """Tests for the select_best_model_fpl function."""

    def test_selects_best_among_multiple(self) -> None:
        y_test = np.array([1, 2, 7, 10, 3, 4, 6, 8, 1, 2,
                           3, 5, 7, 8, 1, 2, 9, 11, 3, 4])
        # Good model: close predictions
        good_preds = y_test + np.random.RandomState(42).normal(0, 0.5, len(y_test))
        # Bad model: random noise
        bad_preds = np.random.RandomState(123).uniform(0, 5, len(y_test))

        best_idx, all_scores = select_best_model_fpl(
            candidate_names=["good", "bad"],
            candidate_predictions=[good_preds, bad_preds],
            y_test=y_test,
        )

        assert best_idx == 0
        assert all_scores[0].model_name == "good"
        assert all_scores[0].composite_score > all_scores[1].composite_score

    def test_ineligible_model_not_selected(self) -> None:
        y_test = np.array([1, 2, 7, 10, 3, 4, 6, 8, 1, 2,
                           3, 5, 7, 8, 1, 2, 9, 11, 3, 4])
        # Model A: good overall but terrible RMSE (artificially inflated)
        preds_a = y_test * 3  # Way off — will fail RMSE gate
        # Model B: decent
        preds_b = y_test + np.random.RandomState(42).normal(0, 0.5, len(y_test))

        best_idx, all_scores = select_best_model_fpl(
            candidate_names=["bad_rmse", "decent"],
            candidate_predictions=[preds_a, preds_b],
            y_test=y_test,
            gates={"rmse": ("<=", 3.0)},
        )

        # The decent model should be selected because bad_rmse fails the gate
        assert best_idx == 1
        assert all_scores[1].eligible is True


# -----------------------------------------------------------------------
# Integration Tests: Automation Pipeline
# -----------------------------------------------------------------------


class TestAutomationCompositePromotion:
    """Tests for composite promotion in the automation pipeline."""

    def test_first_model_always_promoted(
        self,
        isolated_settings: Settings,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """With no existing best model, retraining must promote unconditionally."""
        _patch_network(
            monkeypatch,
            zip_bytes=_build_vaastav_zip(n_gws=10),
            bootstrap=_bootstrap_payload([1, 2, 3]),
            live=_live_payload(3),
        )

        orchestrator = AutomationOrchestrator(isolated_settings)
        result = orchestrator.run(retrain=True, ingest_live=True)

        assert result.retrain_attempted is True
        assert result.retrain_promoted is True
        assert result.new_model_version is not None

        # Verify metadata has FPL metrics
        best_metadata_path = isolated_settings.paths.models_dir / "best_model_metadata.json"
        metadata = json.loads(best_metadata_path.read_text())
        assert "model_name" in metadata
        assert "metrics" in metadata
        # Composite scoring adds extra metric keys
        if "spearman_rho" in metadata["metrics"]:
            assert "recall_6" in metadata["metrics"]
            assert "recall_10" in metadata["metrics"]

    def test_worse_model_not_promoted_composite(
        self,
        isolated_settings: Settings,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A model with artificially perfect metrics should block promotion."""
        _patch_network(
            monkeypatch,
            zip_bytes=_build_vaastav_zip(n_gws=10),
            bootstrap=_bootstrap_payload([1, 2, 3]),
            live=_live_payload(3),
        )

        orchestrator = AutomationOrchestrator(isolated_settings)
        orchestrator.run(retrain=True, ingest_live=True)

        # Make the current best look unbeatable
        best_metadata_path = isolated_settings.paths.models_dir / "best_model_metadata.json"
        metadata = json.loads(best_metadata_path.read_text())
        metadata["metrics"]["mae"] = 0.0000001
        metadata["metrics"]["rmse"] = 0.0000001
        metadata["metrics"]["composite_score"] = 0.9999
        metadata["metrics"]["spearman_rho"] = 0.9999
        metadata["metrics"]["recall_6"] = 0.9999
        best_metadata_path.write_text(json.dumps(metadata))

        best_model_path = isolated_settings.paths.models_dir / "best_model.joblib"
        first_best_bytes = best_model_path.read_bytes()

        result = orchestrator.run(retrain=True, ingest_live=False)

        assert result.retrain_attempted is True
        assert result.retrain_promoted is False
        assert best_model_path.read_bytes() == first_best_bytes

    def test_promotion_reason_recorded(
        self,
        isolated_settings: Settings,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The promotion reason should be recorded in the result."""
        _patch_network(
            monkeypatch,
            zip_bytes=_build_vaastav_zip(n_gws=10),
            bootstrap=_bootstrap_payload([1, 2, 3]),
            live=_live_payload(3),
        )

        orchestrator = AutomationOrchestrator(isolated_settings)
        result = orchestrator.run(retrain=True, ingest_live=True)

        assert result.promotion_reason != ""
        assert any("Promotion decision" in note for note in result.notes)


class TestDryRun:
    """Tests for dry-run mode."""

    def test_dry_run_does_not_promote(
        self,
        isolated_settings: Settings,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """In dry-run mode, no model should be promoted."""
        _patch_network(
            monkeypatch,
            zip_bytes=_build_vaastav_zip(n_gws=10),
            bootstrap=_bootstrap_payload([1, 2, 3]),
            live=_live_payload(3),
        )

        orchestrator = AutomationOrchestrator(isolated_settings)
        result = orchestrator.run(retrain=True, ingest_live=True, dry_run=True)

        assert result.dry_run is True
        assert result.retrain_attempted is True
        assert result.retrain_promoted is False
        assert any("DRY RUN" in note for note in result.notes)

    def test_dry_run_still_versions_data(
        self,
        isolated_settings: Settings,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Dry-run should still version datasets (only model promotion is blocked)."""
        _patch_network(
            monkeypatch,
            zip_bytes=_build_vaastav_zip(n_gws=10),
            bootstrap=_bootstrap_payload([1, 2, 3]),
            live=_live_payload(3),
        )

        orchestrator = AutomationOrchestrator(isolated_settings)
        result = orchestrator.run(retrain=False, ingest_live=True, dry_run=True)

        # Data versioning should still work
        assert result.raw_data_version is not None or result.raw_data_changed is False


class TestIdempotency:
    """Tests for pipeline idempotency."""

    def test_repeated_run_produces_same_data(
        self,
        isolated_settings: Settings,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Running twice with the same data should produce identical datasets."""
        _patch_network(
            monkeypatch,
            zip_bytes=_build_vaastav_zip(n_gws=10),
            bootstrap=_bootstrap_payload([1, 2, 3]),
            live=_live_payload(3),
        )

        orchestrator = AutomationOrchestrator(isolated_settings)

        # First run
        result1 = orchestrator.run(retrain=False, ingest_live=True)

        # Second run with same data
        result2 = orchestrator.run(retrain=False, ingest_live=True)

        # Second run should detect no data change
        assert result2.raw_data_changed is False

    def test_duplicate_ingestion_preserves_row_count(
        self,
        isolated_settings: Settings,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ingesting the same live GW twice should not duplicate rows."""
        _patch_network(
            monkeypatch,
            zip_bytes=_build_vaastav_zip(n_gws=10),
            bootstrap=_bootstrap_payload([1, 2, 3]),
            live=_live_payload(3),
        )

        orchestrator = AutomationOrchestrator(isolated_settings)

        orchestrator.run(retrain=False, ingest_live=True)
        raw_path = isolated_settings.paths.raw_data_dir / "vaastav_merged.csv"
        rows_first = len(pd.read_csv(raw_path))

        orchestrator.run(retrain=False, ingest_live=True)
        rows_second = len(pd.read_csv(raw_path))

        assert rows_second == rows_first


class TestLeakageVerification:
    """Tests verifying no data leakage in feature engineering."""

    def test_rolling_stats_use_shift(self) -> None:
        """Rolling averages must NOT include the current row's value."""
        from src.feature_engineering.steps.rolling_stats import RollingAverageStep
        from src.feature_engineering.models import RollingFeatureSpec

        data = pd.DataFrame({
            "element": [1, 1, 1, 1, 1],
            "GW": [1, 2, 3, 4, 5],
            "total_points": [2, 4, 6, 8, 10],
        })

        spec = RollingFeatureSpec(
            output_name="total_points",
            source_candidates=("total_points",),
            windows=(3,),
        )

        step = RollingAverageStep(
            player_id_columns=("element",),
            chronological_columns=("GW",),
            specs=(spec,),
        )

        result_df, _ = step.apply(data)

        # Row 0 (GW1): shift(1) means no prior data -> NaN
        assert pd.isna(result_df["total_points_avg_last_3"].iloc[0])

        # Row 3 (GW4): shift(1) means window = [GW1, GW2, GW3] = [2, 4, 6]
        # Average should be 4.0, NOT include GW4's value of 8
        assert result_df["total_points_avg_last_3"].iloc[3] == pytest.approx(4.0)

        # Row 4 (GW5): shift(1) means window = [GW2, GW3, GW4] = [4, 6, 8]
        # Average should be 6.0, NOT include GW5's value of 10
        assert result_df["total_points_avg_last_3"].iloc[4] == pytest.approx(6.0)

    def test_target_column_excluded_from_features(self) -> None:
        """The target column must never be used as a feature."""
        from src.training.dataset import select_feature_columns
        from src.config.settings import TrainingSettings

        settings = TrainingSettings()
        data = pd.DataFrame({
            "total_points": [1, 2, 3],
            "minutes": [90, 45, 0],
            "bps": [10, 20, 30],
            "form_index": [0.5, 0.6, 0.7],
        })

        features = select_feature_columns(data, settings)

        assert "total_points" not in features

    def test_same_match_stats_excluded_from_features(self) -> None:
        """Same-match outcome stats (minutes, goals_scored, etc.) must be excluded."""
        from src.training.dataset import select_feature_columns
        from src.config.settings import TrainingSettings

        settings = TrainingSettings()
        data = pd.DataFrame({
            "total_points": [1, 2, 3],
            "minutes": [90, 45, 0],
            "goals_scored": [1, 0, 0],
            "assists": [0, 1, 0],
            "bonus": [3, 1, 0],
            "bps": [25, 15, 5],
            "form_index": [0.5, 0.6, 0.7],
            "total_points_avg_last_3": [2.0, 2.5, 1.5],
        })

        features = select_feature_columns(data, settings)

        # Same-match stats should be excluded
        assert "minutes" not in features
        assert "goals_scored" not in features
        assert "assists" not in features
        assert "bonus" not in features
        assert "bps" not in features

        # Derived features should be included
        assert "form_index" in features
        assert "total_points_avg_last_3" in features


class TestModelVersioning:
    """Tests for model version preservation."""

    def test_model_metadata_backward_compatible(
        self,
        isolated_settings: Settings,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """New metadata fields must not break the existing loader."""
        _patch_network(
            monkeypatch,
            zip_bytes=_build_vaastav_zip(n_gws=10),
            bootstrap=_bootstrap_payload([1, 2, 3]),
            live=_live_payload(3),
        )

        orchestrator = AutomationOrchestrator(isolated_settings)
        orchestrator.run(retrain=True, ingest_live=True)

        from src.prediction.loader import load_model

        best_model_path = isolated_settings.paths.models_dir / "best_model.joblib"
        best_metadata_path = isolated_settings.paths.models_dir / "best_model_metadata.json"

        # This must not raise — the loader must handle new fields gracefully
        loaded = load_model(best_model_path, best_metadata_path)
        assert loaded.model_name is not None
        assert len(loaded.feature_columns) > 0
        assert loaded.target_column == "total_points"


class TestSettingsParsers:
    """Tests for the settings parser helpers."""

    def test_parse_weight_str(self) -> None:
        from src.config.settings import _parse_weight_str

        result = _parse_weight_str("rmse:0.25,mae:0.15,recall_6:0.20")
        assert result == {"rmse": 0.25, "mae": 0.15, "recall_6": 0.20}

    def test_parse_weight_str_empty(self) -> None:
        from src.config.settings import _parse_weight_str

        result = _parse_weight_str("")
        assert result == {}

    def test_parse_gate_str(self) -> None:
        from src.config.settings import _parse_gate_str

        result = _parse_gate_str("rmse:<=:3.0,recall_6:>=:0.05")
        assert result == {"rmse": ("<=", 3.0), "recall_6": (">=", 0.05)}

    def test_parse_gate_str_invalid_operator_ignored(self) -> None:
        from src.config.settings import _parse_gate_str

        result = _parse_gate_str("rmse:==:3.0")
        assert result == {}  # == is not a valid operator


class TestLegacyPromotionStrategy:
    """Tests ensuring the legacy promotion strategy still works."""

    def test_legacy_strategy_selects_by_primary_metric(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """With promotion_strategy='primary_metric', selection should use RMSE."""
        monkeypatch.setenv("FANTASY_AI_DATA_DIR", str(tmp_path / "data"))
        monkeypatch.setenv("FANTASY_AI_MODELS_DIR", str(tmp_path / "models"))
        monkeypatch.setenv("FANTASY_AI_CONFIGS_DIR", str(tmp_path / "configs"))
        monkeypatch.setenv("FANTASY_AI_LOGS_DIR", str(tmp_path / "logs"))
        monkeypatch.setenv("FANTASY_AI_ROLLING_WINDOWS", "3")
        monkeypatch.setenv("FANTASY_AI_TEST_FRACTION", "0.3")
        monkeypatch.setenv("FANTASY_AI_RF_N_ESTIMATORS", "10")
        monkeypatch.setenv("FANTASY_AI_BOOSTED_N_ESTIMATORS", "10")
        monkeypatch.setenv("FANTASY_AI_PROMOTION_STRATEGY", "primary_metric")

        settings = Settings()

        _patch_network(
            monkeypatch,
            zip_bytes=_build_vaastav_zip(n_gws=10),
            bootstrap=_bootstrap_payload([1, 2, 3]),
            live=_live_payload(3),
        )

        orchestrator = AutomationOrchestrator(settings)
        result = orchestrator.run(retrain=True, ingest_live=True)

        assert result.retrain_attempted is True
        assert result.retrain_promoted is True
