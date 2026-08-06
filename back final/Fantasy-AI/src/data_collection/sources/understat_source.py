"""Data source implementation for Understat advanced match statistics.

This source will provide supplementary advanced metrics (xG, xA, shot
maps, etc.) not available in the primary Vaastav dataset, to be merged
in during feature engineering. This module currently contains only the
class skeleton; method bodies are implemented in a future sprint.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data_collection.interfaces.data_source import DataSource, DataSourceMetadata


class UnderstatDataSource(DataSource):
    """Advanced statistics data source backed by Understat.

    Args:
        base_url: Base URL of the Understat website.
        timeout_seconds: Per-request timeout, in seconds.
        max_retries: Maximum number of retry attempts for a failed request.
    """

    def __init__(
        self,
        base_url: str,
        timeout_seconds: int = 30,
        max_retries: int = 3,
    ) -> None:
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries

    @property
    def name(self) -> str:
        """A short, human-readable identifier for this data source."""
        return "understat"

    def download(self, destination: Path) -> DataSourceMetadata:
        """Download advanced statistics from Understat. Implemented in a future sprint."""
        raise NotImplementedError("UnderstatDataSource.download is not yet implemented.")

    def load(self, source_path: Path) -> pd.DataFrame:
        """Load previously downloaded Understat data. Implemented in a future sprint."""
        raise NotImplementedError("UnderstatDataSource.load is not yet implemented.")

    def validate(self, data: pd.DataFrame) -> bool:
        """Structural check of loaded data. Implemented in a future sprint."""
        raise NotImplementedError("UnderstatDataSource.validate is not yet implemented.")

    def update(self, destination: Path) -> DataSourceMetadata:
        """Fetch newly available advanced statistics. Implemented in a future sprint."""
        raise NotImplementedError("UnderstatDataSource.update is not yet implemented.")
