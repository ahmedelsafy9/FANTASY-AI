"""Immutable prediction snapshot storage.

Saves every pre-Gameweek prediction as a complete snapshot of what the model
predicted and what information it used, BEFORE the target Gameweek is played.
Snapshots are never overwritten — this is critical for reproducibility and
for preventing data leakage in the feedback system.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.common.file_utils import ensure_directory
from src.config.logging_config import get_logger

logger = get_logger(__name__)


class PredictionSnapshotStore:
    """Saves and loads immutable prediction snapshots.

    Each snapshot represents the model's prediction for every active player
    for a specific future Gameweek, together with the exact pre-match feature
    vector used by the model.

    Args:
        snapshot_dir: Directory where snapshot CSVs are stored.
    """

    # Metadata columns always present in a snapshot
    META_COLUMNS = (
        "element",
        "name",
        "team",
        "position",
        "season",
        "target_gw",
        "base_prediction",
        "model_name",
        "model_version",
        "prediction_timestamp",
    )

    def __init__(self, snapshot_dir: Path) -> None:
        self._snapshot_dir = snapshot_dir
        ensure_directory(self._snapshot_dir)

    def snapshot_path(self, season: str, gw: int) -> Path:
        """Return the canonical path for a snapshot file.

        Args:
            season: Season identifier (e.g. ``"2026-27"``).
            gw: Target Gameweek number.

        Returns:
            Path: The snapshot CSV path.
        """
        return self._snapshot_dir / f"{season}_GW{gw}.csv"

    def exists(self, season: str, gw: int) -> bool:
        """Check whether a snapshot for the given season/GW already exists."""
        return self.snapshot_path(season, gw).exists()

    def save_snapshot(
        self,
        predictions: pd.DataFrame,
        season: str,
        target_gw: int,
        model_name: str,
        model_version: str,
        prediction_column: str = "predicted_total_points",
        feature_columns: list[str] | None = None,
    ) -> Path:
        """Save an immutable prediction snapshot.

        If a snapshot for this ``(season, target_gw)`` already exists, it is
        NOT overwritten — the existing path is returned with a warning.

        Args:
            predictions: DataFrame with at least ``element`` and the
                prediction column, plus any feature columns to preserve.
            season: Season identifier.
            target_gw: The Gameweek being predicted (future, not yet played).
            model_name: Name of the model that made the prediction.
            model_version: Version identifier of the model.
            prediction_column: Name of the column containing the base
                prediction value.
            feature_columns: If provided, the exact feature columns used by
                the model — these are preserved in the snapshot alongside
                the metadata columns.

        Returns:
            Path: The path to the saved (or existing) snapshot CSV.
        """
        path = self.snapshot_path(season, target_gw)

        if path.exists():
            logger.warning(
                "Snapshot already exists for %s GW%d at %s — NOT overwriting.",
                season,
                target_gw,
                path,
            )
            return path

        timestamp = datetime.now(timezone.utc).isoformat()

        snapshot = pd.DataFrame()

        # Copy metadata columns from predictions if available
        for col in ("element", "name", "team", "position"):
            if col in predictions.columns:
                snapshot[col] = predictions[col].values

        snapshot["season"] = season
        snapshot["target_gw"] = target_gw
        snapshot["base_prediction"] = predictions[prediction_column].values
        snapshot["model_name"] = model_name
        snapshot["model_version"] = model_version
        snapshot["prediction_timestamp"] = timestamp

        # Preserve the exact feature vector used by the model
        if feature_columns:
            for fc in feature_columns:
                if fc in predictions.columns:
                    snapshot[f"feat_{fc}"] = predictions[fc].values

        ensure_directory(path.parent)
        snapshot.to_csv(path, index=False)
        logger.info(
            "Saved prediction snapshot: %s GW%d (%d players) -> %s",
            season,
            target_gw,
            len(snapshot),
            path,
        )
        return path

    def load_snapshot(self, season: str, gw: int) -> pd.DataFrame | None:
        """Load a previously saved snapshot.

        Args:
            season: Season identifier.
            gw: Target Gameweek number.

        Returns:
            pd.DataFrame | None: The snapshot DataFrame, or ``None`` if
            no snapshot exists for this season/GW.
        """
        path = self.snapshot_path(season, gw)
        if not path.exists():
            logger.debug("No snapshot found for %s GW%d.", season, gw)
            return None

        df = pd.read_csv(path, low_memory=False)
        logger.info("Loaded snapshot for %s GW%d: %d rows.", season, gw, len(df))
        return df

    def list_snapshots(self) -> list[tuple[str, int]]:
        """List all available snapshots as (season, gw) tuples.

        Returns:
            list[tuple[str, int]]: Available snapshot identifiers, sorted
            chronologically.
        """
        result = []
        for path in sorted(self._snapshot_dir.glob("*_GW*.csv")):
            stem = path.stem  # e.g. "2026-27_GW2"
            parts = stem.rsplit("_GW", 1)
            if len(parts) == 2:
                try:
                    result.append((parts[0], int(parts[1])))
                except ValueError:
                    continue
        return result
