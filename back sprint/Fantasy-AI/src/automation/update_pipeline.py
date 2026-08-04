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

import pandas as pd

from src.automation.data_versioning import DataVersionManager
from src.automation.merge_live_data import append_live_gameweek
from src.automation.model_versioning import ModelVersionManager
from src.common.file_utils import ensure_directory
from src.config.logging_config import get_logger
from src.config.settings import Settings
from src.core.exceptions import FantasyAIError
from src.data_collection.services.historical_dataset_service import HistoricalDatasetService
from src.data_collection.sources.fpl_api_source import FPLApiDataSource
from src.data_collection.sources.vaastav_source import VaastavDataSource
from src.feature_engineering.factory import build_default_feature_steps
from src.feature_engineering.pipeline import FeaturePipeline
from src.preprocessing.factory import build_default_pipeline_steps
from src.preprocessing.pipeline import PreprocessingPipeline
from src.prediction.loader import load_model
from src.training.dataset import prepare_split_dataset
from src.training.factory import build_default_model_specs
from src.training.persistence import save_best_model
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
        retrain_attempted: Whether retraining was requested for this run.
        retrain_promoted: Whether the newly trained model replaced the
            live "best model" (only possible if ``retrain_attempted``).
        new_model_version: Version ID registered for the newly trained
            model candidate, if retraining ran.
        notes: Any additional human-readable notes about the run.
    """

    generated_at: datetime
    historical_data_updated: bool = False
    live_gameweek_ingested: int | None = None
    raw_data_version: str | None = None
    engineered_data_version: str | None = None
    raw_data_changed: bool = False
    retrain_attempted: bool = False
    retrain_promoted: bool = False
    new_model_version: str | None = None
    notes: list[str] = field(default_factory=list)


class AutomationOrchestrator:
    """Coordinates a full update-and-optionally-retrain run.

    Args:
        settings: Application settings.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def run(self, retrain: bool = False, ingest_live: bool = True) -> AutomationRunResult:
        """Run one full automation cycle.

        Args:
            retrain: If ``True``, retrain candidate models after the
                data refresh and promote the new model only if it
                beats the current best by the configured minimum
                improvement.
            ingest_live: If ``True``, attempt to pull the latest
                finished Gameweek from the live FPL API and merge it
                into the historical dataset before reprocessing.

        Returns:
            AutomationRunResult: A summary of what happened.
        """
        settings = self._settings
        result = AutomationRunResult(generated_at=datetime.now(timezone.utc))

        raw_merged_path = self._refresh_historical_data(settings, ingest_live, result)
        self._version_raw_data(settings, raw_merged_path, result)

        cleaned_path = self._run_preprocessing(settings, raw_merged_path)
        engineered_path = self._run_feature_engineering(settings, cleaned_path)
        self._version_engineered_data(settings, engineered_path, result)

        if retrain:
            self._retrain_and_maybe_promote(settings, engineered_path, result)

        logger.info("Automation run complete: %s", result)
        return result

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    def _refresh_historical_data(
        self, settings: Settings, ingest_live: bool, result: AutomationRunResult
    ) -> Path:
        """Update the Vaastav historical dataset and, optionally, merge live data.

        Args:
            settings: Application settings.
            ingest_live: Whether to also pull the latest live Gameweek.
            result: The in-progress run result, updated in place.

        Returns:
            Path: Path to the refreshed raw merged dataset CSV.
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
        if raw_merged_path.exists():
            try:
                previous_seasons = set(
                    pd.read_csv(raw_merged_path, usecols=["season"], low_memory=False)[
                        "season"
                    ].unique()
                )
            except (ValueError, KeyError):
                pass

        build_result = service.build(
            download_dir=download_dir, raw_dataset_path=raw_merged_path, report_path=report_path
        )
        result.historical_data_updated = bool(set(build_result.seasons) - previous_seasons)

        if not ingest_live:
            result.notes.append("Live Gameweek ingestion was skipped (ingest_live=False).")
            return raw_merged_path

        try:
            fpl_source = FPLApiDataSource(
                base_url=settings.data_sources.fpl_api_base_url,
                events_path=settings.automation.fpl_api_events_path,
                live_event_path_template=settings.automation.fpl_api_live_event_path_template,
                timeout_seconds=settings.data_sources.request_timeout_seconds,
                max_retries=settings.data_sources.request_max_retries,
            )
            live_download_dir = settings.paths.raw_data_dir / "fpl_api"
            fpl_source.update(live_download_dir)
            live_data = fpl_source.load(live_download_dir)
            fpl_source.validate(live_data)

            historical = pd.read_csv(raw_merged_path, low_memory=False)
            merged = append_live_gameweek(
                historical, live_data, duplicate_key_columns=settings.validation.duplicate_key_columns
            )
            merged.to_csv(raw_merged_path, index=False)

            latest_gw = live_data["GW"].iloc[0] if "GW" in live_data.columns else None
            result.live_gameweek_ingested = int(latest_gw) if latest_gw is not None else None
            result.notes.append(f"Merged {len(live_data)} live row(s) into the historical dataset.")
        except FantasyAIError as exc:
            logger.warning("Live Gameweek ingestion failed; continuing with historical data only: %s", exc)
            result.notes.append(f"Live ingestion failed and was skipped: {exc}")

        return raw_merged_path

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

    def _run_preprocessing(self, settings: Settings, raw_merged_path: Path) -> Path:
        """Re-run the preprocessing pipeline (Sprint 4) on the refreshed raw data.

        Args:
            settings: Application settings.
            raw_merged_path: Path to the raw merged dataset CSV.

        Returns:
            Path: Path to the cleaned dataset CSV.
        """
        data = pd.read_csv(raw_merged_path, low_memory=False)
        steps = build_default_pipeline_steps(settings.preprocessing, settings.validation)
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
        steps = build_default_feature_steps(settings.feature_engineering)
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
        self, settings: Settings, engineered_path: Path, result: AutomationRunResult
    ) -> None:
        """Train candidate models and promote the winner only if it's actually better.

        Args:
            settings: Application settings.
            engineered_path: Path to the engineered dataset CSV.
            result: The in-progress run result, updated in place.
        """
        result.retrain_attempted = True
        data = pd.read_csv(engineered_path, low_memory=False)

        try:
            split = prepare_split_dataset(data, settings.training)
        except ValueError as exc:
            result.notes.append(f"Retraining skipped: could not prepare training data: {exc}")
            return

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
        new_metric = getattr(best_result.metrics, settings.training.primary_metric)

        should_promote = True
        if best_model_path.exists() and best_metadata_path.exists():
            try:
                current = load_model(best_model_path, best_metadata_path)
                current_metric = current.metrics.get(settings.training.primary_metric)
                if current_metric is not None:
                    lower_is_better = settings.training.primary_metric in {"mae", "rmse"}
                    improvement = (
                        current_metric - new_metric if lower_is_better else new_metric - current_metric
                    )
                    should_promote = improvement >= settings.automation.retrain_min_improvement
                    result.notes.append(
                        f"Candidate {settings.training.primary_metric}={new_metric:.4f} vs "
                        f"current {current_metric:.4f} (improvement={improvement:.4f})."
                    )
            except FantasyAIError:
                should_promote = True  # No valid existing model to compare against.

        version_manager = ModelVersionManager(
            settings.paths.models_dir / "versions",
            max_versions_to_keep=settings.automation.max_versions_to_keep,
        )
        entry = version_manager.register_model(
            candidate_model_path,
            candidate_metadata_path,
            extra_metadata={
                "model_name": training_result.best_model_name,
                "metrics": {
                    "mae": best_result.metrics.mae,
                    "rmse": best_result.metrics.rmse,
                    "r2": best_result.metrics.r2,
                },
            },
        )
        result.new_model_version = entry.version_id

        if should_promote:
            version_manager.promote_to_best(entry, best_model_path, best_metadata_path)
            result.retrain_promoted = True
            result.notes.append(f"Promoted new model version '{entry.version_id}' to best_model.")
        else:
            result.notes.append(
                f"New model version '{entry.version_id}' registered but NOT promoted "
                "(insufficient improvement over current best)."
            )

        candidate_model_path.unlink(missing_ok=True)
        candidate_metadata_path.unlink(missing_ok=True)
