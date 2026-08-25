"""Orchestrates a full automated update run: refresh data, re-run the
pipeline, version the results, and optionally retrain.

Reuses every pipeline built in prior sprints rather than duplicating
their logic — this module's job is purely coordination and the
Sprint 9-specific concerns (live ingestion, versioning, promote-only-
if-better retraining).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from src.automation.data_versioning import DataVersionManager
from src.automation.merge_live_data import append_live_gameweek
from src.automation.model_versioning import ModelVersionManager
from src.common.file_utils import ensure_directory
from src.config.logging_config import get_logger
from src.config.settings import Settings
from src.core.exceptions import FantasyAIError
from src.data_collection.services.historical_dataset_service import HistoricalDatasetService
from src.data_collection.services.team_mapping_service import TeamMappingService
from src.data_collection.sources.fpl_api_source import FPLApiDataSource
from src.data_collection.sources.vaastav_source import VaastavDataSource
from src.feature_engineering.factory import build_default_feature_steps
from src.feature_engineering.pipeline import FeaturePipeline
from src.preprocessing.factory import build_default_pipeline_steps
from src.preprocessing.pipeline import PreprocessingPipeline
from src.prediction.export import export_predictions
from src.prediction.loader import load_model
from src.prediction.next_gameweek import build_next_gameweek_rows
from src.prediction.predictor import PredictionService
from src.training.dataset import prepare_split_dataset
from src.training.factory import build_default_model_specs
from src.training.persistence import save_best_model
from src.training.promotion_scorer import compute_fpl_metrics
from src.training.report_writer import write_comparison_report
from src.training.trainer import ModelTrainer

logger = get_logger(__name__)


@dataclass
class AutomationRunResult:
    """Summary of one automated update run.

    Attributes:
        generated_at: When the run finished.
        historical_data_updated: Whether new Vaastav season data was found.
        live_gameweek_ingested: The live-ingested Gameweek number, if any.
        raw_data_version: Version ID registered for the raw merged dataset.
        engineered_data_version: Version ID registered for the engineered dataset.
        raw_data_changed: Whether the raw dataset actually changed since
            the last snapshot (a new version is only registered if so).
        opponent_mapping_teams: Number of teams in the ID->name mapping
            used to resolve a numeric ``opponent_team`` column, or 0 if
            no mapping was available for this run (opponent_strength
            will then still be skipped, per the existing safe fallback).
        retrain_attempted: Whether retraining was requested for this run.
        retrain_promoted: Whether the newly trained model replaced the
            live "best model" (only possible if ``retrain_attempted``).
        new_model_version: Version ID registered for the newly trained
            model candidate, if retraining ran.
        promotion_reason: Human-readable explanation of the promotion
            decision.
        dry_run: Whether this run was in dry-run mode (no model
            promotion or file writes for promotion).
        notes: Any additional human-readable notes about the run.
    """

    generated_at: datetime
    historical_data_updated: bool = False
    live_gameweek_ingested: int | None = None
    raw_data_version: str | None = None
    engineered_data_version: str | None = None
    raw_data_changed: bool = False
    opponent_mapping_teams: int = 0
    retrain_attempted: bool = False
    retrain_promoted: bool = False
    new_model_version: str | None = None
    promotion_reason: str = ""
    dry_run: bool = False
    notes: list[str] = field(default_factory=list)


class AutomationOrchestrator:
    """Coordinates a full update-and-optionally-retrain run.

    Args:
        settings: Application settings.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def run(
        self,
        retrain: bool = False,
        ingest_live: bool = True,
        dry_run: bool | None = None,
    ) -> AutomationRunResult:
        """Run one full automation cycle.

        Args:
            retrain: If ``True``, retrain candidate models after the
                data refresh and promote the new model only if it
                beats the current best by the configured minimum
                improvement.
            ingest_live: If ``True``, attempt to pull the latest
                finished Gameweek from the live FPL API and merge it
                into the historical dataset before reprocessing.
            dry_run: If ``True``, evaluate everything but do not
                promote models. Overrides settings if provided.

        Returns:
            AutomationRunResult: A summary of what happened.
        """
        settings = self._settings
        result = AutomationRunResult(generated_at=datetime.now(timezone.utc))

        # Resolve dry_run: explicit argument > settings > False
        is_dry_run = dry_run if dry_run is not None else settings.automation.dry_run
        result.dry_run = is_dry_run
        if is_dry_run:
            logger.info("=== DRY RUN MODE — no model promotion will occur ===")

        raw_merged_path, team_mapping = self._refresh_historical_data(settings, ingest_live, result)
        self._version_raw_data(settings, raw_merged_path, result)

        cleaned_path = self._run_preprocessing(settings, raw_merged_path, team_mapping)
        engineered_path = self._run_feature_engineering(settings, cleaned_path)
        self._version_engineered_data(settings, engineered_path, result)

        if retrain:
            self._retrain_and_maybe_promote(settings, engineered_path, result, is_dry_run)

        self._export_predictions(settings, engineered_path)

        logger.info("Automation run complete: %s", result)
        return result

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    def _refresh_historical_data(
        self, settings: Settings, ingest_live: bool, result: AutomationRunResult
    ) -> tuple[Path, dict[int, str] | None]:
        """Update the Vaastav historical dataset and, optionally, merge live data.

        Also fetches (or falls back to a cached) team-ID -> name mapping
        from the live FPL API — this is what fixes the opponent_strength
        domain-mismatch issue: see
        :mod:`src.data_collection.services.team_mapping_service`.

        Args:
            settings: Application settings.
            ingest_live: Whether to also pull the latest live Gameweek.
            result: The in-progress run result, updated in place.

        Returns:
            tuple[Path, dict[int, str] | None]: Path to the refreshed
            raw merged dataset CSV, and the team-ID -> name mapping (or
            ``None`` if unavailable this run).
        """
        vaastav_source = VaastavDataSource(
            repo_url=settings.data_sources.vaastav_repo_url,
            seasons=settings.data_sources.vaastav_seasons,
            timeout_seconds=settings.data_sources.request_timeout_seconds,
            max_retries=settings.data_sources.request_max_retries,
        )
        service = HistoricalDatasetService(data_source=vaastav_source)

        raw_merged_path = settings.paths.raw_data_dir / "vaastav_merged.csv"
        report_path = settings.paths.raw_data_dir / "vaastav_metadata_report.md"
        download_dir = settings.paths.raw_data_dir / "vaastav"

        previous_seasons: set[str] = set()
        rows_before = 0
        if raw_merged_path.exists():
            try:
                existing = pd.read_csv(raw_merged_path, low_memory=False)
                previous_seasons = set(existing["season"].unique()) if "season" in existing.columns else set()
                rows_before = len(existing)
                logger.info(
                    "Existing dataset: %d rows, seasons=%s",
                    rows_before,
                    sorted(previous_seasons),
                )
            except (ValueError, KeyError):
                pass

        build_result = service.build(
            download_dir=download_dir, raw_dataset_path=raw_merged_path, report_path=report_path
        )
        result.historical_data_updated = bool(set(build_result.seasons) - previous_seasons)

        # Log post-build statistics
        if raw_merged_path.exists():
            rows_after = len(pd.read_csv(raw_merged_path, usecols=[0], low_memory=False))
            logger.info(
                "Post-build dataset: %d rows (delta=%+d)",
                rows_after,
                rows_after - rows_before,
            )

        mapping_service = TeamMappingService(
            settings.paths.external_data_dir / settings.fixture_aware.team_mapping_cache_path
        )
        team_mapping = mapping_service.load()

        if not ingest_live:
            result.notes.append("Live Gameweek ingestion was skipped (ingest_live=False).")
            if team_mapping:
                result.opponent_mapping_teams = len(team_mapping)
            return raw_merged_path, team_mapping

        try:
            fpl_source = FPLApiDataSource(
                base_url=settings.data_sources.fpl_api_base_url,
                events_path=settings.automation.fpl_api_events_path,
                live_event_path_template=settings.automation.fpl_api_live_event_path_template,
                fixtures_path=settings.automation.fpl_api_fixtures_path,
                timeout_seconds=settings.data_sources.request_timeout_seconds,
                max_retries=settings.data_sources.request_max_retries,
            )
            live_download_dir = settings.paths.raw_data_dir / "fpl_api"
            new_metadata = fpl_source.update(live_download_dir)
            latest_finished_event = new_metadata.extra.get("latest_finished_event")

            teams = fpl_source.get_teams(live_download_dir)
            team_mapping = mapping_service.build_mapping(teams)
            mapping_service.save(team_mapping)
            result.opponent_mapping_teams = len(team_mapping)

            if latest_finished_event is None:
                logger.info(
                    "No finished Gameweek found in current season yet; "
                    "reference data updated, live match stats merge skipped."
                )
                result.notes.append(
                    "No finished Gameweek found in current season yet; "
                    "live match stats merge skipped."
                )
                return raw_merged_path, team_mapping

            live_data = fpl_source.load(live_download_dir)
            fpl_source.validate(live_data)

            # Idempotency check: detect if this GW was already ingested
            latest_gw = live_data["GW"].iloc[0] if "GW" in live_data.columns else None
            if latest_gw is not None and raw_merged_path.exists():
                existing = pd.read_csv(raw_merged_path, low_memory=False)
                if "GW" in existing.columns:
                    existing_gws = set(existing["GW"].unique())
                    if int(latest_gw) in existing_gws:
                        logger.info(
                            "GW %d already present in dataset (%d existing GWs). "
                            "Merge will deduplicate.",
                            int(latest_gw),
                            len(existing_gws),
                        )

            historical = pd.read_csv(raw_merged_path, low_memory=False)
            rows_before_merge = len(historical)
            merged = append_live_gameweek(
                historical, live_data, duplicate_key_columns=settings.validation.duplicate_key_columns
            )
            merged.to_csv(raw_merged_path, index=False)

            result.live_gameweek_ingested = int(latest_gw) if latest_gw is not None else None
            logger.info(
                "Live merge: %d rows before, %d live rows, %d rows after (delta=%+d)",
                rows_before_merge,
                len(live_data),
                len(merged),
                len(merged) - rows_before_merge,
            )
            result.notes.append(f"Merged {len(live_data)} live row(s) into the historical dataset.")
        except FantasyAIError as exc:
            logger.warning("Live Gameweek ingestion failed; continuing with historical data only: %s", exc)
            result.notes.append(f"Live ingestion failed and was skipped: {exc}")
            if team_mapping:
                result.opponent_mapping_teams = len(team_mapping)
                result.notes.append(
                    f"Using cached team mapping ({len(team_mapping)} teams) from a previous run."
                )

        return raw_merged_path, team_mapping

    def _version_raw_data(
        self, settings: Settings, raw_merged_path: Path, result: AutomationRunResult
    ) -> None:
        """Snapshot the raw merged dataset if it changed since the last snapshot.

        Args:
            settings: Application settings.
            raw_merged_path: Path to the raw merged dataset CSV.
            result: The in-progress run result, updated in place.
        """
        manager = DataVersionManager(
            settings.paths.data_dir / "versions" / "raw",
            max_versions_to_keep=settings.automation.max_versions_to_keep,
        )
        if not manager.has_changed_since_last_snapshot(raw_merged_path):
            logger.info("Raw dataset unchanged since last snapshot; skipping versioning.")
            result.raw_data_changed = False
            return

        row_count = len(pd.read_csv(raw_merged_path, usecols=[0], low_memory=False))
        entry = manager.snapshot(raw_merged_path, {"row_count": row_count})
        result.raw_data_changed = True
        result.raw_data_version = entry.version_id

    def _run_preprocessing(
        self, settings: Settings, raw_merged_path: Path, team_mapping: dict[int, str] | None
    ) -> Path:
        """Re-run the preprocessing pipeline (Sprint 4) on the refreshed raw data.

        Args:
            settings: Application settings.
            raw_merged_path: Path to the raw merged dataset CSV.
            team_mapping: Team-ID -> name mapping used to normalize a
                numeric ``opponent_team`` column, if available.

        Returns:
            Path: Path to the cleaned dataset CSV.
        """
        data = pd.read_csv(raw_merged_path, low_memory=False)
        vaastav_data_dir = settings.paths.raw_data_dir / "vaastav" / "data"
        steps = build_default_pipeline_steps(
            settings.preprocessing,
            settings.validation,
            team_id_mapping=team_mapping,
            vaastav_data_dir=vaastav_data_dir if vaastav_data_dir.exists() else None,
        )
        pipeline_result = PreprocessingPipeline(steps=steps).run(data)

        cleaned_path = settings.paths.processed_data_dir / "vaastav_cleaned.csv"
        ensure_directory(cleaned_path.parent)
        pipeline_result.data.to_csv(cleaned_path, index=False)
        return cleaned_path

    def _run_feature_engineering(self, settings: Settings, cleaned_path: Path) -> Path:
        """Re-run the feature engineering pipeline (Sprint 5) on the cleaned data.

        Args:
            settings: Application settings.
            cleaned_path: Path to the cleaned dataset CSV.

        Returns:
            Path: Path to the engineered dataset CSV.
        """
        data = pd.read_csv(cleaned_path, low_memory=False)
        steps = build_default_feature_steps(settings.feature_engineering, settings.fixture_aware)
        pipeline_result = FeaturePipeline(steps=steps).run(data)

        engineered_path = settings.paths.processed_data_dir / "vaastav_features.csv"
        ensure_directory(engineered_path.parent)
        pipeline_result.data.to_csv(engineered_path, index=False)
        return engineered_path

    def _version_engineered_data(
        self, settings: Settings, engineered_path: Path, result: AutomationRunResult
    ) -> None:
        """Snapshot the engineered dataset if it changed since the last snapshot.

        Args:
            settings: Application settings.
            engineered_path: Path to the engineered dataset CSV.
            result: The in-progress run result, updated in place.
        """
        manager = DataVersionManager(
            settings.paths.data_dir / "versions" / "engineered",
            max_versions_to_keep=settings.automation.max_versions_to_keep,
        )
        if not manager.has_changed_since_last_snapshot(engineered_path):
            logger.info("Engineered dataset unchanged since last snapshot; skipping versioning.")
            return

        row_count = len(pd.read_csv(engineered_path, usecols=[0], low_memory=False))
        entry = manager.snapshot(engineered_path, {"row_count": row_count})
        result.engineered_data_version = entry.version_id

    def _retrain_and_maybe_promote(
        self,
        settings: Settings,
        engineered_path: Path,
        result: AutomationRunResult,
        dry_run: bool = False,
    ) -> None:
        """Train candidate models and promote the winner only if it's actually better.

        Uses the configured promotion strategy:
        - ``"composite"`` (default): FPL-aware multi-metric scoring.
        - ``"primary_metric"``: Legacy single-metric comparison.

        Args:
            settings: Application settings.
            engineered_path: Path to the engineered dataset CSV.
            result: The in-progress run result, updated in place.
            dry_run: If True, evaluate but do not promote.
        """
        result.retrain_attempted = True
        data = pd.read_csv(engineered_path, low_memory=False)

        # Log training data diagnostics
        if "GW" in data.columns:
            gw_min = int(data["GW"].min())
            gw_max = int(data["GW"].max())
            logger.info(
                "Training data: %d rows, GW range=[%d, %d]",
                len(data), gw_min, gw_max,
            )
        if "season" in data.columns:
            seasons = sorted(data["season"].dropna().unique())
            logger.info("Training data seasons: %s", seasons)

        try:
            split = prepare_split_dataset(data, settings.training)
        except ValueError as exc:
            result.notes.append(f"Retraining skipped: could not prepare training data: {exc}")
            return

        logger.info(
            "Training split: %d train rows, %d test rows, %d features",
            len(split.X_train), len(split.X_test), len(split.feature_columns),
        )

        model_specs, skipped_models = build_default_model_specs(settings.training)
        trainer = ModelTrainer(model_specs=model_specs, settings=settings.training)
        try:
            training_result = trainer.run(split, skipped_models)
        except RuntimeError as exc:
            result.notes.append(f"Retraining failed: {exc}")
            return

        candidate_model_path = settings.paths.models_dir / "_candidate_model.joblib"
        candidate_metadata_path = settings.paths.models_dir / "_candidate_model_metadata.json"
        save_best_model(training_result, split, candidate_model_path, candidate_metadata_path)

        report_path = settings.paths.models_dir / "model_comparison_report.md"
        write_comparison_report(training_result, report_path)

        best_model_path = settings.paths.models_dir / "best_model.joblib"
        best_metadata_path = settings.paths.models_dir / "best_model_metadata.json"

        best_result = next(
            r for r in training_result.results if r.name == training_result.best_model_name
        )

        # ---------------------------------------------------------------
        # Promotion decision
        # ---------------------------------------------------------------
        should_promote = True
        promotion_reason = "First model — no prior best to compare against."

        if best_model_path.exists() and best_metadata_path.exists():
            try:
                current = load_model(best_model_path, best_metadata_path)

                if settings.training.promotion_strategy == "composite":
                    should_promote, promotion_reason = self._composite_promotion_check(
                        training_result, best_result, current, settings
                    )
                else:
                    should_promote, promotion_reason = self._legacy_promotion_check(
                        best_result, current, settings
                    )

            except FantasyAIError:
                should_promote = True
                promotion_reason = "No valid existing model to compare against."

        result.promotion_reason = promotion_reason
        result.notes.append(f"Promotion decision: {promotion_reason}")

        # ---------------------------------------------------------------
        # Dry-run gate
        # ---------------------------------------------------------------
        if dry_run:
            should_promote = False
            result.notes.append(
                "DRY RUN: model would have been promoted but dry-run mode prevented it."
                if should_promote else
                "DRY RUN: model evaluated but not promoted (dry-run mode)."
            )

        # ---------------------------------------------------------------
        # Version and maybe promote
        # ---------------------------------------------------------------
        version_metadata = {
            "model_name": training_result.best_model_name,
            "metrics": {
                "mae": best_result.metrics.mae,
                "rmse": best_result.metrics.rmse,
                "r2": best_result.metrics.r2,
            },
            "promotion_reason": promotion_reason,
        }

        # Add FPL metrics to version metadata if composite scoring was used
        if training_result.composite_scores:
            for score in training_result.composite_scores:
                if score.model_name == best_result.name:
                    version_metadata["fpl_metrics"] = score.fpl_metrics.to_dict()
                    version_metadata["composite_score"] = score.composite_score
                    version_metadata["eligible"] = score.eligible
                    break

        version_manager = ModelVersionManager(
            settings.paths.models_dir / "versions",
            max_versions_to_keep=settings.automation.max_versions_to_keep,
        )
        entry = version_manager.register_model(
            candidate_model_path,
            candidate_metadata_path,
            extra_metadata=version_metadata,
        )
        result.new_model_version = entry.version_id

        if should_promote:
            version_manager.promote_to_best(entry, best_model_path, best_metadata_path)
            result.retrain_promoted = True
            result.notes.append(f"Promoted new model version '{entry.version_id}' to best_model.")
        else:
            result.notes.append(
                f"New model version '{entry.version_id}' registered but NOT promoted "
                f"({promotion_reason})."
            )

        candidate_model_path.unlink(missing_ok=True)
        candidate_metadata_path.unlink(missing_ok=True)

    def _composite_promotion_check(
        self,
        training_result,
        best_result,
        current,
        settings: Settings,
    ) -> tuple[bool, str]:
        """Check whether the new model beats the current best using composite scoring.

        Args:
            training_result: Full training result with composite scores.
            best_result: The best new candidate's ModelResult.
            current: The currently deployed LoadedModel.
            settings: Application settings.

        Returns:
            tuple[bool, str]: (should_promote, reason).
        """
        # Find the new model's composite score
        new_composite = 0.0
        new_fpl = None
        for score in training_result.composite_scores:
            if score.model_name == best_result.name:
                new_composite = score.composite_score
                new_fpl = score.fpl_metrics
                break

        # Compute FPL metrics for the current best model using the same test set
        if training_result.y_test is not None and best_result.predictions is not None:
            # Load current model and predict on the same test features
            # We compare using the new candidate's FPL metrics vs current's known metrics
            current_rmse = current.metrics.get("rmse")
            current_mae = current.metrics.get("mae")
            current_recall_6 = current.metrics.get("recall_6")
            current_spearman = current.metrics.get("spearman_rho")

            if new_fpl is not None:
                improvements = []
                regressions = []

                if current_rmse is not None:
                    if new_fpl.rmse < current_rmse:
                        improvements.append(f"RMSE {current_rmse:.4f}→{new_fpl.rmse:.4f}")
                    elif new_fpl.rmse > current_rmse:
                        regressions.append(f"RMSE {current_rmse:.4f}→{new_fpl.rmse:.4f}")

                if current_mae is not None:
                    if new_fpl.mae < current_mae:
                        improvements.append(f"MAE {current_mae:.4f}→{new_fpl.mae:.4f}")
                    elif new_fpl.mae > current_mae:
                        regressions.append(f"MAE {current_mae:.4f}→{new_fpl.mae:.4f}")

                if current_recall_6 is not None:
                    if new_fpl.recall_6 > current_recall_6:
                        improvements.append(f"≥6recall {current_recall_6:.4f}→{new_fpl.recall_6:.4f}")
                    elif new_fpl.recall_6 < current_recall_6:
                        regressions.append(f"≥6recall {current_recall_6:.4f}→{new_fpl.recall_6:.4f}")

                if current_spearman is not None:
                    if new_fpl.spearman_rho > current_spearman:
                        improvements.append(
                            f"Spearman {current_spearman:.4f}→{new_fpl.spearman_rho:.4f}"
                        )
                    elif new_fpl.spearman_rho < current_spearman:
                        regressions.append(
                            f"Spearman {current_spearman:.4f}→{new_fpl.spearman_rho:.4f}"
                        )

                # Decision: promote if there are improvements and no critical regressions
                # The composite score already handles this, but we need a simple yes/no
                # Use the min_improvement threshold on composite score
                min_improvement = settings.automation.retrain_min_improvement

                # If current model has no composite score, the new one always wins
                current_composite = current.metrics.get("composite_score", None)

                if current_composite is not None:
                    improvement = new_composite - current_composite
                    should_promote = improvement >= min_improvement
                    reason = (
                        f"Composite score: {current_composite:.4f}→{new_composite:.4f} "
                        f"(Δ={improvement:+.4f}, threshold={min_improvement}). "
                        f"Improvements: [{', '.join(improvements) or 'none'}]. "
                        f"Regressions: [{', '.join(regressions) or 'none'}]."
                    )
                else:
                    # Current model was trained with legacy strategy — promote if new
                    # composite score indicates improvement on key metrics
                    should_promote = True
                    reason = (
                        f"Current model lacks composite score (legacy). "
                        f"New composite={new_composite:.4f}. "
                        f"Improvements: [{', '.join(improvements) or 'none'}]. "
                        f"Regressions: [{', '.join(regressions) or 'none'}]."
                    )

                logger.info("Composite promotion check: %s", reason)
                return should_promote, reason

        # Fallback to legacy if composite scoring data is unavailable
        return self._legacy_promotion_check(best_result, current, settings)

    def _legacy_promotion_check(
        self,
        best_result,
        current,
        settings: Settings,
    ) -> tuple[bool, str]:
        """Legacy single-metric promotion check.

        Args:
            best_result: The best new candidate's ModelResult.
            current: The currently deployed LoadedModel.
            settings: Application settings.

        Returns:
            tuple[bool, str]: (should_promote, reason).
        """
        metric_name = settings.training.primary_metric
        new_metric = getattr(best_result.metrics, metric_name)
        current_metric = current.metrics.get(metric_name)

        if current_metric is None:
            return True, f"Current model has no {metric_name} recorded."

        lower_is_better = metric_name in {"mae", "rmse"}
        improvement = (
            current_metric - new_metric if lower_is_better else new_metric - current_metric
        )
        should_promote = improvement >= settings.automation.retrain_min_improvement

        reason = (
            f"Candidate {metric_name}={new_metric:.4f} vs "
            f"current {current_metric:.4f} "
            f"(improvement={improvement:.4f}, "
            f"threshold={settings.automation.retrain_min_improvement})."
        )
        return should_promote, reason

    def _export_predictions(self, settings: Settings, engineered_path: Path) -> Path | None:
        """Generate and export the canonical predictions.csv artifact if a model is available.

        Args:
            settings: Application settings.
            engineered_path: Path to the engineered features CSV.

        Returns:
            Path | None: Path to predictions.csv if generated, else None.
        """
        model_path = settings.paths.models_dir / "best_model.joblib"
        metadata_path = settings.paths.models_dir / "best_model_metadata.json"
        if not model_path.exists() or not metadata_path.exists():
            logger.info("No deployed model found; skipping automated prediction export.")
            return None

        try:
            loaded_model = load_model(model_path, metadata_path)
            data = pd.read_csv(engineered_path, low_memory=False)
            next_gw_rows = build_next_gameweek_rows(
                data,
                player_id_columns=settings.feature_engineering.player_id_columns,
                chronological_columns=settings.feature_engineering.chronological_columns,
                max_valid_gameweek=settings.prediction.max_valid_gameweek,
            )
            service = PredictionService(loaded_model)
            predictions = service.predict(next_gw_rows)
            output_path = settings.paths.processed_data_dir / "predictions.csv"
            prediction_column = f"predicted_{loaded_model.target_column}"
            export_predictions(
                predictions,
                id_columns=settings.prediction.export_id_columns,
                prediction_column=prediction_column,
                output_path=output_path,
            )
            logger.info(
                "Automated prediction export complete: %d prediction(s) saved to %s.",
                len(predictions),
                output_path,
            )
            return output_path
        except FantasyAIError as exc:
            logger.warning("Automated prediction export failed; skipping: %s", exc)
            return None
        except Exception as exc:
            logger.warning("Unexpected error during automated prediction export: %s", exc)
            return None

