"""Service orchestrating the end-to-end historical dataset ingestion.

This service depends only on the abstract
:class:`~src.data_collection.interfaces.data_source.DataSource`
interface (injected via the constructor), never on a concrete
implementation. It coordinates downloading, loading, validating,
persisting, and reporting on a dataset — logic that does not belong
inside any single ``DataSource`` implementation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.common.file_utils import ensure_directory
from src.config.logging_config import get_logger
from src.core.exceptions import DataSourceError
from src.data_collection.interfaces.data_source import DataSource, DataSourceMetadata

logger = get_logger(__name__)


@dataclass
class IngestionResult:
    """Outcome of a full historical dataset ingestion run.

    Attributes:
        raw_dataset_path: Path the merged raw dataset was saved to.
        report_path: Path the metadata report was saved to.
        row_count: Total number of rows in the merged dataset.
        column_count: Total number of columns in the merged dataset.
        seasons: Seasons included in the merged dataset.
        source_metadata: Metadata returned by the underlying
            ``DataSource.download()`` call.
    """

    raw_dataset_path: Path
    report_path: Path
    row_count: int
    column_count: int
    seasons: tuple[str, ...]
    source_metadata: DataSourceMetadata = field(repr=False)


class HistoricalDatasetService:
    """Coordinates a :class:`DataSource` to build a merged historical dataset.

    Args:
        data_source: Any object implementing the :class:`DataSource`
            interface. The service never depends on a concrete class.
    """

    def __init__(self, data_source: DataSource) -> None:
        self._data_source = data_source

    def build(
        self,
        download_dir: Path,
        raw_dataset_path: Path,
        report_path: Path,
    ) -> IngestionResult:
        """Run the full download -> load -> validate -> save -> report pipeline.

        Args:
            download_dir: Directory the data source should download
                its raw, per-season files into.
            raw_dataset_path: File path the single merged dataset
                should be written to (CSV).
            report_path: File path the metadata report should be
                written to (Markdown).

        Returns:
            IngestionResult: Summary of the ingestion run.

        Raises:
            DataSourceError: If any pipeline stage fails.
        """
        logger.info("Starting historical dataset ingestion via '%s'.", self._data_source.name)

        source_metadata = self._data_source.download(download_dir)
        merged = self._data_source.load(download_dir)
        self._data_source.validate(merged)

        self._save_dataset(merged, raw_dataset_path)
        seasons = self._extract_seasons(merged)
        self._write_report(merged, seasons, source_metadata, report_path)

        result = IngestionResult(
            raw_dataset_path=raw_dataset_path,
            report_path=report_path,
            row_count=len(merged),
            column_count=merged.shape[1],
            seasons=seasons,
            source_metadata=source_metadata,
        )
        logger.info(
            "Ingestion complete: %d rows, %d columns, %d season(s).",
            result.row_count,
            result.column_count,
            len(result.seasons),
        )
        return result

    @staticmethod
    def _extract_seasons(data: pd.DataFrame) -> tuple[str, ...]:
        """Extract the sorted, unique set of seasons present in the data.

        Args:
            data: Merged dataset containing a ``season`` column.

        Returns:
            tuple[str, ...]: Sorted unique season identifiers.

        Raises:
            DataSourceError: If no ``season`` column is present.
        """
        if "season" not in data.columns:
            raise DataSourceError("Merged dataset has no 'season' column.")
        return tuple(sorted(data["season"].dropna().unique().tolist()))

    @staticmethod
    def _save_dataset(data: pd.DataFrame, raw_dataset_path: Path) -> None:
        """Persist the merged dataset to disk as CSV.

        Args:
            data: Merged dataset to persist.
            raw_dataset_path: Destination file path.
        """
        ensure_directory(raw_dataset_path.parent)
        data.to_csv(raw_dataset_path, index=False)
        logger.info("Saved merged raw dataset to %s.", raw_dataset_path)

    @staticmethod
    def _write_report(
        data: pd.DataFrame,
        seasons: tuple[str, ...],
        source_metadata: DataSourceMetadata,
        report_path: Path,
    ) -> None:
        """Write a human-readable Markdown metadata report.

        Args:
            data: Merged dataset the report describes.
            seasons: Seasons included in the dataset.
            source_metadata: Metadata returned by the data source.
            report_path: Destination file path for the report.
        """
        ensure_directory(report_path.parent)

        per_season_counts = (
            data.groupby("season").size().reindex(seasons).fillna(0).astype(int)
        )
        null_percentages = (data.isna().mean() * 100).round(2).sort_values(ascending=False)

        lines: list[str] = [
            "# Fantasy-AI — Historical Dataset Report",
            "",
            f"Generated: {datetime.now(timezone.utc).isoformat()}",
            f"Data source: `{source_metadata.name}` ({source_metadata.source_url})",
            "",
            "## Summary",
            "",
            f"- Total rows: **{len(data)}**",
            f"- Total columns: **{data.shape[1]}**",
            f"- Seasons included: **{len(seasons)}** ({', '.join(seasons)})",
            "",
            "## Rows per Season",
            "",
            "| Season | Rows |",
            "|--------|------|",
        ]
        for season, count in per_season_counts.items():
            lines.append(f"| {season} | {count} |")

        lines += [
            "",
            "## Columns with Missing Values (top 15)",
            "",
            "| Column | % Missing |",
            "|--------|-----------|",
        ]
        for column, pct in null_percentages.head(15).items():
            lines.append(f"| {column} | {pct}% |")

        lines += [
            "",
            "## Source Metadata",
            "",
            "```json",
            json.dumps(
                {
                    "branch": source_metadata.extra.get("branch"),
                    "retrieved_at": (
                        source_metadata.retrieved_at.isoformat()
                        if source_metadata.retrieved_at
                        else None
                    ),
                },
                indent=2,
            ),
            "```",
            "",
        ]

        report_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Wrote metadata report to %s.", report_path)
