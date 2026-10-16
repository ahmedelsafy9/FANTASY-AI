"""Immutable prediction ledger.

Original forecasts are never overwritten. Feedback-corrected values are
stored as additional columns / successor versions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.common.file_utils import atomic_write_csv, ensure_directory
from src.config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class LedgerRecord:
    """One prediction row in the ledger."""

    entity_type: str
    entity_id: str
    season: str
    target_gameweek: int
    prediction_cutoff: str | None
    raw_prediction: float | None
    calibrated_prediction: float | None
    feedback_corrected_prediction: float | None
    actual_outcome: float | None
    model_version: str
    feature_schema_version: str
    data_source_timestamp: str | None
    correction_model_version: str | None
    evaluation_status: str
    recorded_at: str


class PredictionLedger:
    """Append-only store of prediction records."""

    def __init__(self, ledger_dir: Path) -> None:
        self._dir = ledger_dir
        ensure_directory(self._dir)

    def path_for(self, season: str, gameweek: int) -> Path:
        return self._dir / f"{season}_GW{gameweek}_ledger.csv"

    def append_records(self, season: str, gameweek: int, records: list[LedgerRecord]) -> Path:
        """Append records. Existing original rows are never replaced."""
        path = self.path_for(season, gameweek)
        frame = pd.DataFrame([asdict(record) for record in records])
        if path.exists():
            existing = pd.read_csv(path)
            combined = pd.concat([existing, frame], ignore_index=True)
        else:
            combined = frame
        atomic_write_csv(combined, path)
        logger.info("Ledger wrote %d rows to %s", len(frame), path)
        return path

    def attach_outcomes(
        self,
        season: str,
        gameweek: int,
        outcomes: pd.DataFrame,
        id_column: str = "entity_id",
        outcome_column: str = "actual_outcome",
    ) -> Path:
        """Fill actual outcomes on existing rows without changing raw_prediction."""
        path = self.path_for(season, gameweek)
        if not path.exists():
            raise FileNotFoundError(f"No ledger for {season} GW{gameweek}")
        existing = pd.read_csv(path)
        merged = existing.merge(
            outcomes[[id_column, outcome_column]].rename(columns={id_column: "entity_id"}),
            on="entity_id",
            how="left",
            suffixes=("", "_new"),
        )
        if "actual_outcome_new" in merged.columns:
            merged["actual_outcome"] = merged["actual_outcome"].combine_first(
                merged["actual_outcome_new"]
            )
            merged = merged.drop(columns=["actual_outcome_new"])
        merged.loc[merged["actual_outcome"].notna(), "evaluation_status"] = "outcome_attached"
        atomic_write_csv(merged, path)
        return path


def records_from_prediction_frame(
    predictions: pd.DataFrame,
    *,
    season: str,
    target_gameweek: int,
    model_version: str,
    feature_schema_version: str,
    prediction_cutoff: str | None = None,
    data_source_timestamp: str | None = None,
    id_column: str = "element",
    raw_column: str = "predicted_expected_points",
    calibrated_column: str | None = None,
) -> list[LedgerRecord]:
    """Build ledger records from an inference frame without mutating it."""
    now = datetime.now(timezone.utc).isoformat()
    records: list[LedgerRecord] = []
    for _, row in predictions.iterrows():
        records.append(
            LedgerRecord(
                entity_type="player",
                entity_id=str(row.get(id_column, "")),
                season=season,
                target_gameweek=int(target_gameweek),
                prediction_cutoff=prediction_cutoff,
                raw_prediction=_optional_float(row.get(raw_column)),
                calibrated_prediction=_optional_float(row.get(calibrated_column)) if calibrated_column else None,
                feedback_corrected_prediction=None,
                actual_outcome=None,
                model_version=model_version,
                feature_schema_version=feature_schema_version,
                data_source_timestamp=data_source_timestamp,
                correction_model_version=None,
                evaluation_status="predicted",
                recorded_at=now,
            )
        )
    return records


def _optional_float(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
