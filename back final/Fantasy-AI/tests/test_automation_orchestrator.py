"""End-to-end integration tests for AutomationOrchestrator.

All network access (Vaastav repo zip download, live FPL API) is
mocked. This exercises the full Sprint 9 chain: refresh -> version ->
preprocess -> engineer features -> version -> (optionally) retrain ->
promote-only-if-better, using the real pipeline classes from every
prior sprint.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from src.automation.update_pipeline import AutomationOrchestrator
from src.config.settings import Settings

VAASTAV_REPO_URL = "https://github.com/vaastav/Fantasy-Premier-League"
FPL_API_BASE_URL = "https://fantasy.premierleague.com/api"


def _build_vaastav_zip(n_gws: int = 5, season: str = "2022-23") -> bytes:
    rows = ["name,GW,element,total_points,minutes,bonus,bps,ict_index,was_home,value,team,opponent_team,kickoff_time"]
    teams = ["Arsenal", "Chelsea"]
    for gw in range(1, n_gws + 1):
        for element, name in ((1, "Player One"), (2, "Player Two")):
            rows.append(
                f"{name},{gw},{element},{5 + gw % 3},90,1,20,5.0,True,50,"
                f"{teams[element % 2]},{teams[(element + 1) % 2]},2022-08-{gw:02d}T14:00:00Z"
            )
    csv_text = "\n".join(rows) + "\n"

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(f"Fantasy-Premier-League-master/data/{season}/gws/merged_gw.csv", csv_text)
    return buffer.getvalue()


def _build_vaastav_zip_with_numeric_opponents(n_gws: int = 5, season: str = "2022-23") -> bytes:
    """Like _build_vaastav_zip, but opponent_team is a numeric team ID —
    reproducing the exact reported bug scenario (team=name, opponent_team=ID)."""
    rows = ["name,GW,element,total_points,minutes,bonus,bps,ict_index,was_home,value,team,opponent_team,kickoff_time"]
    team_names = ["Arsenal", "Chelsea"]
    team_ids = [11, 12]  # must match _bootstrap_payload's teams list below
    for gw in range(1, n_gws + 1):
        for element, name in ((1, "Player One"), (2, "Player Two")):
            rows.append(
                f"{name},{gw},{element},{5 + gw % 3},90,1,20,5.0,True,50,"
                f"{team_names[element % 2]},{team_ids[(element + 1) % 2]},2022-08-{gw:02d}T14:00:00Z"
            )
    csv_text = "\n".join(rows) + "\n"

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(f"Fantasy-Premier-League-master/data/{season}/gws/merged_gw.csv", csv_text)
    return buffer.getvalue()


def _bootstrap_payload(finished_events: list[int]) -> dict[str, Any]:
    events = [
        {"id": i, "finished": i in finished_events, "deadline_time": "2022-09-16T10:00:00Z"}
        for i in range(1, 8)
    ]
    return {
        "events": events,
        "teams": [{"id": 11, "name": "Arsenal"}, {"id": 12, "name": "Chelsea"}],
        "elements": [
            {"id": 1, "web_name": "Player One", "team": 11, "now_cost": 55},
            {"id": 2, "web_name": "Player Two", "team": 12, "now_cost": 60},
        ],
    }


def _live_payload(gw: int) -> dict[str, Any]:
    return {
        "elements": [
            {"id": 1, "stats": {"minutes": 90, "goals_scored": 1, "total_points": 12}},
            {"id": 2, "stats": {"minutes": 90, "goals_scored": 0, "total_points": 4}},
        ]
    }


class _FakeHttpResponse:
    def __init__(self, content: Any, status_code: int = 200, is_json: bool = False) -> None:
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
    """Build Settings rooted at an isolated tmp_path, with small/fast pipeline params."""
    monkeypatch.setenv("FANTASY_AI_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FANTASY_AI_MODELS_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("FANTASY_AI_CONFIGS_DIR", str(tmp_path / "configs"))
    monkeypatch.setenv("FANTASY_AI_LOGS_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("FANTASY_AI_ROLLING_WINDOWS", "3")
    monkeypatch.setenv("FANTASY_AI_TEST_FRACTION", "0.3")
    monkeypatch.setenv("FANTASY_AI_RF_N_ESTIMATORS", "10")
    monkeypatch.setenv("FANTASY_AI_BOOSTED_N_ESTIMATORS", "10")
    return Settings()


def _patch_network(
    monkeypatch: pytest.MonkeyPatch,
    zip_bytes: bytes | None = None,
    bootstrap: dict | None = None,
    live: dict | None = None,
) -> None:
    """Patch `requests.get` once for both VaastavDataSource and FPLApiDataSource.

    Both sources do `import requests` and call `requests.get(...)`, so they
    share the exact same module object — patching `requests.get` via either
    source's module path patches the identical attribute. Patching it twice
    (once per source) silently makes the second patch win for *both* sources,
    which previously broke VaastavDataSource's call (it passes `stream=True`,
    which the FPL API fake didn't accept). One dispatching patch avoids that.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        zip_bytes: Response body for the Vaastav repo zip download, if the
            test needs it reachable.
        bootstrap: Response body for the FPL API bootstrap-static endpoint,
            if the test needs it reachable.
        live: Response body for the FPL API live-event endpoint, if the
            test needs it reachable.
    """

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


def test_run_without_retrain_produces_versioned_data(
    isolated_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A basic run (no retrain) must refresh, merge live data, and version datasets."""
    _patch_network(
        monkeypatch,
        zip_bytes=_build_vaastav_zip(),
        bootstrap=_bootstrap_payload([1, 2, 3]),
        live=_live_payload(3),
    )

    orchestrator = AutomationOrchestrator(isolated_settings)
    result = orchestrator.run(retrain=False, ingest_live=True)

    assert result.historical_data_updated is True
    assert result.live_gameweek_ingested == 3
    assert result.raw_data_changed is True
    assert result.raw_data_version is not None
    assert result.engineered_data_version is not None
    assert result.retrain_attempted is False

    engineered_path = isolated_settings.paths.processed_data_dir / "vaastav_features.csv"
    assert engineered_path.exists()
    engineered = pd.read_csv(engineered_path)
    assert len(engineered) > 0
    # The live-ingested Gameweek 3 row must have overridden the historical one.
    assert (engineered["total_points"] == 12).any()


def test_run_skips_live_ingestion_when_disabled(
    isolated_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ingest_live=False must skip the live API entirely."""
    _patch_network(monkeypatch, zip_bytes=_build_vaastav_zip())

    orchestrator = AutomationOrchestrator(isolated_settings)
    result = orchestrator.run(retrain=False, ingest_live=False)

    assert result.live_gameweek_ingested is None
    assert any("skipped" in note.lower() for note in result.notes)


def test_run_with_retrain_promotes_first_model_with_no_prior_best(
    isolated_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no existing best model, retraining must promote the new one unconditionally."""
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

    best_model_path = isolated_settings.paths.models_dir / "best_model.joblib"
    best_metadata_path = isolated_settings.paths.models_dir / "best_model_metadata.json"
    assert best_model_path.exists()
    assert best_metadata_path.exists()

    metadata = json.loads(best_metadata_path.read_text())
    assert "model_name" in metadata
    assert "feature_columns" in metadata


def test_run_with_retrain_does_not_promote_a_worse_model(
    isolated_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second retrain run must not demote a better existing best model."""
    _patch_network(
        monkeypatch,
        zip_bytes=_build_vaastav_zip(n_gws=10),
        bootstrap=_bootstrap_payload([1, 2, 3]),
        live=_live_payload(3),
    )

    orchestrator = AutomationOrchestrator(isolated_settings)
    orchestrator.run(retrain=True, ingest_live=True)

    best_model_path = isolated_settings.paths.models_dir / "best_model.joblib"
    first_best_bytes = best_model_path.read_bytes()

    # Artificially make the current best model look unbeatable by rewriting its
    # metadata with near-perfect metrics, then re-run retraining: it must not promote.
    best_metadata_path = isolated_settings.paths.models_dir / "best_model_metadata.json"
    metadata = json.loads(best_metadata_path.read_text())
    metadata["metrics"]["mae"] = 0.0000001
    metadata["metrics"]["rmse"] = 0.0000001
    metadata["metrics"]["spearman_rho"] = 0.9999
    metadata["metrics"]["recall_6"] = 0.9999
    metadata["metrics"]["recall_10"] = 0.9999
    metadata["metrics"]["precision_6"] = 0.9999
    metadata["metrics"]["composite_score"] = 0.9999
    best_metadata_path.write_text(json.dumps(metadata))

    result = orchestrator.run(retrain=True, ingest_live=False)

    assert result.retrain_attempted is True
    assert result.retrain_promoted is False
    assert best_model_path.read_bytes() == first_best_bytes  # unchanged


def test_run_fixes_opponent_strength_domain_mismatch_end_to_end(
    isolated_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression test for the exact reported bug: with numeric opponent_team
    IDs in the historical data, a full automation run (which fetches and
    applies the live team-ID mapping) must produce a populated
    opponent_strength column — not an all-NaN/skipped one.
    """
    _patch_network(
        monkeypatch,
        zip_bytes=_build_vaastav_zip_with_numeric_opponents(n_gws=8),
        bootstrap=_bootstrap_payload([1, 2, 3]),
        live=_live_payload(3),
    )

    orchestrator = AutomationOrchestrator(isolated_settings)
    result = orchestrator.run(retrain=False, ingest_live=True)

    # The mapping must have actually been fetched and used.
    assert result.opponent_mapping_teams == 2

    engineered_path = isolated_settings.paths.processed_data_dir / "vaastav_features.csv"
    engineered = pd.read_csv(engineered_path)

    assert engineered["opponent_strength"].notna().any(), (
        "opponent_strength is still all-NaN — the domain-mismatch fix did not take effect"
    )


def test_run_exports_canonical_predictions_if_model_present(
    isolated_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When a trained model is present, an automation run must automatically
    export an updated canonical predictions.csv matching the new features."""
    import joblib
    from sklearn.linear_model import LinearRegression

    _patch_network(
        monkeypatch,
        zip_bytes=_build_vaastav_zip(n_gws=5),
        bootstrap=_bootstrap_payload([1, 2]),
        live=_live_payload(2),
    )

    # Place a dummy model in models_dir
    model = LinearRegression().fit([[90.0]], [5.0])
    isolated_settings.paths.models_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, isolated_settings.paths.models_dir / "best_model.joblib")
    (isolated_settings.paths.models_dir / "best_model_metadata.json").write_text(
        json.dumps(
            {
                "model_name": "linear_regression",
                "feature_columns": ["minutes_avg_last_3"],
                "target_column": "total_points",
                "train_medians": {"minutes_avg_last_3": 80.0},
                "metrics": {"mae": 1.0, "rmse": 1.5, "r2": 0.5},
            }
        ),
        encoding="utf-8",
    )

    orchestrator = AutomationOrchestrator(isolated_settings)
    orchestrator.run(retrain=False, ingest_live=True)

    predictions_path = isolated_settings.paths.processed_data_dir / "predictions.csv"
    assert predictions_path.exists(), "predictions.csv was not exported by the automation run"

    preds = pd.read_csv(predictions_path)
    assert len(preds) == 2
    assert "predicted_total_points" in preds.columns
    assert "predicted_for_gw" in preds.columns
    assert (preds["predicted_for_gw"] == 6).all()  # Latest GW in zip was 5, so next is 6

