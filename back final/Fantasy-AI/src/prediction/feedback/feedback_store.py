"""Feedback store: joins prediction snapshots with actual Gameweek results.

After a Gameweek is completed, this module compares what the model predicted
against what actually happened, creating a feedback record that captures the
prediction error AND the actual match statistics that generated the player's
real FPL points. These actual stats are preserved as *observed contribution
factors* — they explain HOW the actual points were generated, but must NEVER
be used as input features when predicting that same Gameweek.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.common.file_utils import atomic_write_csv, ensure_directory
from src.config.logging_config import get_logger

logger = get_logger(__name__)

# Actual match statistics to preserve in feedback records.
# These explain HOW the FPL points were generated.
ACTUAL_STAT_COLUMNS = (
    "total_points",
    "minutes",
    "goals_scored",
    "assists",
    "clean_sheets",
    "goals_conceded",
    "own_goals",
    "penalties_saved",
    "penalties_missed",
    "yellow_cards",
    "red_cards",
    "saves",
    "bonus",
    "bps",
    "ict_index",
    "influence",
    "creativity",
    "threat",
    "expected_goals",
    "expected_assists",
    "expected_goal_involvements",
    "starts",
    "was_home",
)


class FeedbackStore:
    """Generates and persists feedback records.

    Joins prediction snapshots with actual Gameweek data to create
    structured feedback records capturing prediction errors and the
    actual performance statistics that generated the real points.

    Args:
        feedback_dir: Directory where feedback CSVs are stored.
    """

    def __init__(self, feedback_dir: Path) -> None:
        self._feedback_dir = feedback_dir
        ensure_directory(self._feedback_dir)

    def feedback_path(self, season: str, gw: int) -> Path:
        """Return the canonical path for a feedback file.

        Args:
            season: Season identifier.
            gw: Gameweek number.

        Returns:
            Path: The feedback CSV path.
        """
        return self._feedback_dir / f"{season}_GW{gw}_feedback.csv"

    def exists(self, season: str, gw: int) -> bool:
        """Check whether feedback for the given season/GW already exists."""
        return self.feedback_path(season, gw).exists()

    def generate_feedback(
        self,
        snapshot: pd.DataFrame,
        actual_data: pd.DataFrame,
        season: str,
        gw: int,
    ) -> pd.DataFrame:
        """Generate feedback by joining a prediction snapshot with actual results.

        This is **idempotent** — running it twice for the same GW will
        overwrite the previous feedback file (regenerate, not duplicate).

        Args:
            snapshot: The prediction snapshot for this GW (from
                :class:`PredictionSnapshotStore`).
            actual_data: The actual Gameweek data containing real results.
                Must have ``element`` and ``total_points`` columns at minimum.
            season: Season identifier.
            gw: Gameweek number.

        Returns:
            pd.DataFrame: The feedback records.
        """
        if "element" not in snapshot.columns:
            raise ValueError("Snapshot must contain 'element' column.")
        if "element" not in actual_data.columns:
            raise ValueError("Actual data must contain 'element' column.")

        # Filter actual data to this season/GW
        actual_gw = actual_data.copy()
        if "season" in actual_gw.columns:
            actual_gw = actual_gw[actual_gw["season"] == season]
        if "GW" in actual_gw.columns:
            actual_gw = actual_gw[
                pd.to_numeric(actual_gw["GW"], errors="coerce") == gw
            ]

        if actual_gw.empty:
            logger.warning(
                "No actual data found for %s GW%d — cannot generate feedback.",
                season,
                gw,
            )
            return pd.DataFrame()

        # Deduplicate actual data by element (prefer last occurrence)
        actual_gw = actual_gw.drop_duplicates(subset="element", keep="last")

        # Join on element (stable player ID)
        snap_cols = ["element", "base_prediction"]
        if "name" in snapshot.columns:
            snap_cols.append("name")
        if "team" in snapshot.columns:
            snap_cols.append("team")
        if "position" in snapshot.columns:
            snap_cols.append("position")
        if "model_name" in snapshot.columns:
            snap_cols.append("model_name")
        if "model_version" in snapshot.columns:
            snap_cols.append("model_version")

        # Also include any feature columns stored in the snapshot
        feat_cols = [c for c in snapshot.columns if c.startswith("feat_")]
        snap_cols.extend(feat_cols)

        # Deduplicate snapshot by element
        snap_deduped = snapshot[snap_cols].drop_duplicates(
            subset="element", keep="last"
        )

        merged = snap_deduped.merge(
            actual_gw,
            on="element",
            how="inner",
            suffixes=("_snap", "_actual"),
        )

        if merged.empty:
            logger.warning(
                "No matching players between snapshot and actual data for %s GW%d.",
                season,
                gw,
            )
            return pd.DataFrame()

        # Calculate error metrics
        predicted = merged["base_prediction"]
        actual_pts = pd.to_numeric(merged["total_points"], errors="coerce").fillna(0)

        feedback = pd.DataFrame()
        feedback["element"] = merged["element"].values

        # Copy identity columns
        for col in ("name", "team", "position"):
            # Prefer actual data columns, fallback to snapshot
            actual_col = f"{col}_actual" if f"{col}_actual" in merged.columns else col
            snap_col = f"{col}_snap" if f"{col}_snap" in merged.columns else col
            if actual_col in merged.columns:
                feedback[col] = merged[actual_col].values
            elif snap_col in merged.columns:
                feedback[col] = merged[snap_col].values
            elif col in merged.columns:
                feedback[col] = merged[col].values

        feedback["season"] = season
        feedback["GW"] = gw
        feedback["predicted_points"] = predicted.values
        feedback["actual_points"] = actual_pts.values
        feedback["prediction_error"] = (actual_pts - predicted).values
        feedback["absolute_error"] = feedback["prediction_error"].abs().values
        feedback["squared_error"] = (feedback["prediction_error"] ** 2).values

        # Error direction
        feedback["error_direction"] = "exact"
        feedback.loc[feedback["prediction_error"] > 0, "error_direction"] = (
            "underprediction"
        )
        feedback.loc[feedback["prediction_error"] < 0, "error_direction"] = (
            "overprediction"
        )

        # Copy model info
        if "model_name" in merged.columns:
            feedback["model_name"] = merged["model_name"].values
        if "model_version" in merged.columns:
            feedback["model_version"] = merged["model_version"].values

        # Preserve actual match statistics (observed contribution factors)
        for stat_col in ACTUAL_STAT_COLUMNS:
            if stat_col in merged.columns and stat_col != "total_points":
                feedback[f"actual_{stat_col}"] = pd.to_numeric(
                    merged[stat_col], errors="coerce"
                ).values

        # Preserve pre-match feature values from snapshot
        for fc in feat_cols:
            if fc in merged.columns:
                feedback[fc] = merged[fc].values

        # Save — idempotent (overwrites existing)
        path = self.feedback_path(season, gw)
        atomic_write_csv(feedback, path)
        logger.info(
            "Generated feedback for %s GW%d: %d records, "
            "MAE=%.3f, mean_error=%.3f -> %s",
            season,
            gw,
            len(feedback),
            feedback["absolute_error"].mean(),
            feedback["prediction_error"].mean(),
            path,
        )
        return feedback

    def load_feedback(
        self,
        season: str | None = None,
        max_gw: int | None = None,
    ) -> pd.DataFrame:
        """Load accumulated feedback records.

        Args:
            season: If provided, only load feedback for this season.
            max_gw: If provided, only load feedback for GWs <= this value.
                Used to enforce temporal ordering (no leakage).

        Returns:
            pd.DataFrame: Combined feedback records, sorted by GW.
        """
        frames = []
        for path in sorted(self._feedback_dir.glob("*_feedback.csv")):
            stem = path.stem  # e.g. "2026-27_GW2_feedback"
            parts = stem.split("_GW")
            if len(parts) < 2:
                continue
            file_season = parts[0]
            try:
                file_gw = int(parts[1].replace("_feedback", ""))
            except ValueError:
                continue

            if season is not None and file_season != season:
                continue
            if max_gw is not None and file_gw > max_gw:
                continue

            try:
                df = pd.read_csv(path, low_memory=False)
                frames.append(df)
            except Exception as exc:
                logger.warning("Could not read feedback file %s: %s", path, exc)

        if not frames:
            return pd.DataFrame()

        combined = pd.concat(frames, ignore_index=True)
        if "GW" in combined.columns:
            combined = combined.sort_values("GW").reset_index(drop=True)
        logger.info(
            "Loaded %d feedback records (%d files).",
            len(combined),
            len(frames),
        )
        return combined

    def list_feedback(self) -> list[tuple[str, int]]:
        """List all available feedback as (season, gw) tuples.

        Returns:
            list[tuple[str, int]]: Available feedback identifiers, sorted.
        """
        result = []
        for path in sorted(self._feedback_dir.glob("*_feedback.csv")):
            stem = path.stem
            parts = stem.split("_GW")
            if len(parts) < 2:
                continue
            try:
                gw = int(parts[1].replace("_feedback", ""))
                result.append((parts[0], gw))
            except ValueError:
                continue
        return result
