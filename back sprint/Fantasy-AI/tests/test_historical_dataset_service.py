"""Unit tests for HistoricalDatasetService.

A fake DataSource test double is used so this test depends only on the
abstract interface, mirroring how the service itself depends on it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from src.core.exceptions import DataSourceError
from src.data_collection.interfaces.data_source import DataSource, DataSourceMetadata
from src.data_collection.services.historical_dataset_service import (
    HistoricalDatasetService,
)


class _FakeDataSource(DataSource):
    """In-memory DataSource double for testing the orchestration service."""

    def __init__(self, data: pd.DataFrame, should_fail_validate: bool = False) -> None:
        self._data = data
        self._should_fail_validate = should_fail_validate
        self.download_called_with: Path | None = None

    @property
    def name(self) -> str:
        return "fake_source"

    def download(self, destination: Path) -> DataSourceMetadata:
        self.download_called_with = destination
        return DataSourceMetadata(
            name=self.name,
            source_url="https://example.com/fake",
            retrieved_at=datetime.now(timezone.utc),
            extra={"branch": "master"},
        )

    def load(self, source_path: Path) -> pd.DataFrame:
        return self._data

    def validate(self, data: pd.DataFrame) -> bool:
        if self._should_fail_validate:
            raise DataSourceError("fake validation failure")
        return True

    def update(self, destination: Path) -> DataSourceMetadata:
        return self.download(destination)


@pytest.fixture
def sample_data() -> pd.DataFrame:
    """A small two-season merged dataset."""
    return pd.DataFrame(
        {
            "season": ["2021-22", "2021-22", "2022-23"],
            "name": ["Player A", "Player A", "Player B"],
            "total_points": [10, 5, None],
        }
    )


def test_build_saves_dataset_and_report(tmp_path: Path, sample_data: pd.DataFrame) -> None:
    """build() must save a merged CSV and a Markdown report describing it."""
    source = _FakeDataSource(sample_data)
    service = HistoricalDatasetService(data_source=source)

    raw_dataset_path = tmp_path / "merged.csv"
    report_path = tmp_path / "report.md"

    result = service.build(
        download_dir=tmp_path / "downloads",
        raw_dataset_path=raw_dataset_path,
        report_path=report_path,
    )

    assert result.row_count == 3
    assert result.seasons == ("2021-22", "2022-23")
    assert raw_dataset_path.exists()
    assert report_path.exists()

    saved = pd.read_csv(raw_dataset_path)
    assert len(saved) == 3

    report_text = report_path.read_text(encoding="utf-8")
    assert "2021-22" in report_text
    assert "total_points" in report_text


def test_build_propagates_validation_failures(tmp_path: Path, sample_data: pd.DataFrame) -> None:
    """build() must propagate errors raised by the underlying source's validate()."""
    source = _FakeDataSource(sample_data, should_fail_validate=True)
    service = HistoricalDatasetService(data_source=source)

    with pytest.raises(DataSourceError):
        service.build(
            download_dir=tmp_path / "downloads",
            raw_dataset_path=tmp_path / "merged.csv",
            report_path=tmp_path / "report.md",
        )


def test_build_raises_when_season_column_missing(tmp_path: Path) -> None:
    """build() must raise a clear error if the merged data has no season column."""
    source = _FakeDataSource(pd.DataFrame({"name": ["x"], "total_points": [1]}))
    service = HistoricalDatasetService(data_source=source)

    with pytest.raises(DataSourceError):
        service.build(
            download_dir=tmp_path / "downloads",
            raw_dataset_path=tmp_path / "merged.csv",
            report_path=tmp_path / "report.md",
        )


def test_build_calls_download_with_provided_directory(
    tmp_path: Path, sample_data: pd.DataFrame
) -> None:
    """build() must forward the download_dir argument to the source's download()."""
    source = _FakeDataSource(sample_data)
    service = HistoricalDatasetService(data_source=source)
    download_dir = tmp_path / "downloads"

    service.build(
        download_dir=download_dir,
        raw_dataset_path=tmp_path / "merged.csv",
        report_path=tmp_path / "report.md",
    )

    assert source.download_called_with == download_dir
