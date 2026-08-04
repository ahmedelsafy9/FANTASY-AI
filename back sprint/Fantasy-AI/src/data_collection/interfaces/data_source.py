"""Abstract interface for all FPL data sources.

This module defines the single contract (:class:`DataSource`) that the
rest of the application depends on. Concrete implementations (e.g. for
the Vaastav historical repository, the official FPL API, or Understat)
live in ``src/data_collection/sources`` and must never be imported
directly by business logic — only this interface should be referenced
outside the data collection layer.

This is the cornerstone of the project's Dependency Inversion: high
level modules (preprocessing, feature engineering, training, ...)
depend on this abstraction, never on a concrete data source, so a new
provider can be added, or an existing one swapped out, without
touching any other layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class DataSourceMetadata:
    """Descriptive metadata about a data source and its last operation.

    Attributes:
        name: Human-readable identifier for the data source.
        source_url: Origin URL the data was retrieved from.
        retrieved_at: Timestamp of the most recent successful
            ``download`` or ``update`` call, if any.
        records_count: Number of records available after the last
            ``load`` call, if known.
        extra: Free-form dictionary for source-specific metadata
            (e.g. detected seasons, HTTP status codes, file hashes).
    """

    name: str
    source_url: str
    retrieved_at: datetime | None = None
    records_count: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class DataSource(ABC):
    """Abstract base class every concrete data source must implement.

    A ``DataSource`` is responsible for the full lifecycle of acquiring
    and exposing data from a single external origin: downloading raw
    data, loading it into memory, validating its structural integrity,
    and refreshing it with newly available records.

    Implementations must not leak provider-specific details (file
    formats, endpoints, authentication, etc.) through this interface —
    callers only ever see the methods defined here.
    """

    @abstractmethod
    def download(self, destination: Path) -> DataSourceMetadata:
        """Download raw data from the source into ``destination``.

        Args:
            destination: Directory the raw data should be written to.
                Implementations must create the directory if it does
                not already exist.

        Returns:
            DataSourceMetadata: Metadata describing what was downloaded.

        Raises:
            src.core.exceptions.DataSourceError: If the download fails.
        """
        raise NotImplementedError

    @abstractmethod
    def load(self, source_path: Path) -> pd.DataFrame:
        """Load previously downloaded raw data into a DataFrame.

        Args:
            source_path: Directory or file previously produced by
                :meth:`download`.

        Returns:
            pd.DataFrame: The loaded, un-processed data.

        Raises:
            src.core.exceptions.DataSourceError: If the data cannot be
                located or parsed.
        """
        raise NotImplementedError

    @abstractmethod
    def validate(self, data: pd.DataFrame) -> bool:
        """Perform a lightweight structural check on loaded data.

        This is a fast, source-specific sanity check (e.g. expected
        columns are present) — it is distinct from, and simpler than,
        the full validation pipeline implemented in the ``preprocessing``
        layer during Sprint 3.

        Args:
            data: DataFrame previously produced by :meth:`load`.

        Returns:
            bool: ``True`` if the data passes the structural check.

        Raises:
            src.core.exceptions.DataValidationError: If validation
                fails in a way that should halt the pipeline.
        """
        raise NotImplementedError

    @abstractmethod
    def update(self, destination: Path) -> DataSourceMetadata:
        """Refresh previously downloaded data with newly available records.

        Args:
            destination: Directory containing data previously written
                by :meth:`download`, to be incrementally updated.

        Returns:
            DataSourceMetadata: Metadata describing the update.

        Raises:
            src.core.exceptions.DataSourceError: If the update fails.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        """A short, human-readable identifier for this data source."""
        raise NotImplementedError
