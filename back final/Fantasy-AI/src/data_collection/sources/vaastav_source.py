"""Data source implementation for the Vaastav Fantasy-Premier-League repository.

Repository: https://github.com/vaastav/Fantasy-Premier-League

This is the sole source of historical FPL data used by the project.
Data is retrieved by downloading the repository as a zip archive (no
``git`` binary dependency), extracting only the ``data/`` directory
(one subdirectory per season), and merging each season's
``gws/merged_gw.csv`` file into a single DataFrame.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from src.common.decorators import retry
from src.common.file_utils import (
    ensure_directory,
    extract_zip,
    read_csv_robust,
    replace_directory,
)
from src.common.season_utils import detect_seasons, filter_requested_seasons
from src.config.logging_config import get_logger
from src.core.exceptions import DataSourceError, DataValidationError
from src.data_collection.interfaces.data_source import DataSource, DataSourceMetadata

logger = get_logger(__name__)

_CANDIDATE_BRANCHES: tuple[str, ...] = ("master", "main")
_METADATA_FILENAME = "_vaastav_metadata.json"
_MERGED_GW_FILENAME = "merged_gw.csv"
_GWS_SUBDIR = "gws"


class VaastavDataSource(DataSource):
    """Historical FPL data source backed by the Vaastav GitHub repository.

    Args:
        repo_url: URL of the Vaastav Fantasy-Premier-League repository.
        seasons: Specific seasons to restrict operations to (e.g.
            ``("2022-23", "2023-24")``). When empty, all seasons found
            in the repository are used — no season is ever hardcoded.
        timeout_seconds: Per-request timeout, in seconds.
        max_retries: Maximum number of retry attempts for a failed
            download request.
    """

    def __init__(
        self,
        repo_url: str,
        seasons: tuple[str, ...] = (),
        timeout_seconds: int = 30,
        max_retries: int = 3,
    ) -> None:
        self._repo_url = repo_url.rstrip("/")
        self._seasons = seasons
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries

    @property
    def name(self) -> str:
        """A short, human-readable identifier for this data source."""
        return "vaastav"

    # ------------------------------------------------------------------
    # DataSource interface
    # ------------------------------------------------------------------

    def download(self, destination: Path) -> DataSourceMetadata:
        """Download and extract the Vaastav repository's ``data/`` directory.

        Args:
            destination: Directory the season data should be written
                to (as ``destination/data/<season>/...``). Created if
                it does not already exist.

        Returns:
            DataSourceMetadata: Metadata describing the downloaded
            seasons and retrieval timestamp.

        Raises:
            DataSourceError: If the repository cannot be downloaded or
                no season data is found after extraction.
        """
        ensure_directory(destination)

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            tmp_dir = Path(tmp_dir_name)
            zip_path = tmp_dir / "repo.zip"
            branch_used = self._download_zip(zip_path)

            extraction_dir = tmp_dir / "extracted"
            extract_zip(zip_path, extraction_dir)

            repo_root = self._find_extracted_repo_root(extraction_dir)
            source_data_dir = repo_root / "data"
            if not source_data_dir.exists():
                raise DataSourceError(
                    f"Extracted repository at {repo_root} has no 'data' directory."
                )

            target_data_dir = destination / "data"
            replace_directory(source_data_dir, target_data_dir)

        available_seasons = detect_seasons(target_data_dir)
        if not available_seasons:
            raise DataSourceError(
                f"No valid season directories detected under {target_data_dir}."
            )

        metadata = DataSourceMetadata(
            name=self.name,
            source_url=self._repo_url,
            retrieved_at=datetime.now(timezone.utc),
            records_count=None,
            extra={
                "branch": branch_used,
                "available_seasons": list(available_seasons),
            },
        )
        self._write_metadata(destination, metadata)
        logger.info(
            "Downloaded %s: %d season(s) detected (%s).",
            self.name,
            len(available_seasons),
            ", ".join(available_seasons),
        )
        return metadata

    def load(self, source_path: Path) -> pd.DataFrame:
        """Load and merge Gameweek data for all requested seasons.

        Args:
            source_path: Directory previously populated by
                :meth:`download` (expected to contain a ``data``
                subdirectory with one folder per season).

        Returns:
            pd.DataFrame: Combined data for every selected season, with
            an added ``season`` column identifying the origin of each
            row.

        Raises:
            DataSourceError: If no season data can be found or loaded.
        """
        data_dir = source_path / "data"
        available_seasons = detect_seasons(data_dir)
        if not available_seasons:
            raise DataSourceError(
                f"No season directories found under {data_dir}. "
                "Call download() first."
            )

        seasons_to_load = filter_requested_seasons(available_seasons, self._seasons)
        if not seasons_to_load:
            raise DataSourceError(
                f"None of the requested seasons {self._seasons} are available "
                f"in {data_dir}. Available seasons: {available_seasons}."
            )

        frames: list[pd.DataFrame] = []
        for season in seasons_to_load:
            frame = self._load_season(data_dir / season, season)
            if frame is not None and not frame.empty:
                frames.append(frame)
            else:
                logger.warning("Season %s produced no rows; skipping.", season)

        if not frames:
            raise DataSourceError(
                f"Loaded zero rows across seasons {seasons_to_load}."
            )

        combined = pd.concat(frames, ignore_index=True, sort=False)
        logger.info(
            "Loaded %d total rows across %d season(s).", len(combined), len(frames)
        )
        return combined

    def validate(self, data: pd.DataFrame) -> bool:
        """Perform a lightweight structural check on loaded data.

        Args:
            data: DataFrame previously produced by :meth:`load`.

        Returns:
            bool: ``True`` if the data passes the structural check.

        Raises:
            DataValidationError: If the data is empty or missing
                critical columns.
        """
        if data.empty:
            raise DataValidationError("Loaded Vaastav dataset is empty.")

        required_columns = {"season", "total_points"}
        missing = required_columns - set(data.columns)
        if missing:
            raise DataValidationError(
                f"Vaastav dataset is missing required columns: {sorted(missing)}."
            )

        gw_column = "GW" if "GW" in data.columns else (
            "round" if "round" in data.columns else None
        )
        if gw_column is not None:
            out_of_range = data[
                (data[gw_column] < 1) | (data[gw_column] > 38)
            ]
            if not out_of_range.empty:
                logger.warning(
                    "%d row(s) have a %s value outside the expected 1-38 range.",
                    len(out_of_range),
                    gw_column,
                )

        duplicate_count = int(data.duplicated().sum())
        if duplicate_count:
            logger.warning("%d fully duplicate row(s) detected.", duplicate_count)

        logger.info("Validation passed: %d rows, %d columns.", *data.shape)
        return True

    def update(self, destination: Path) -> DataSourceMetadata:
        """Re-download the repository and report what changed.

        Args:
            destination: Directory previously populated by
                :meth:`download`, to be refreshed in place.

        Returns:
            DataSourceMetadata: Metadata describing the update,
            including the previously known season list for comparison.

        Raises:
            DataSourceError: If the refresh fails.
        """
        previous_metadata = self._read_metadata(destination)
        previous_seasons = tuple(
            previous_metadata.get("extra", {}).get("available_seasons", [])
            if previous_metadata
            else ()
        )

        new_metadata = self.download(destination)

        new_seasons = tuple(new_metadata.extra.get("available_seasons", []))
        added_seasons = tuple(s for s in new_seasons if s not in previous_seasons)

        new_metadata.extra["previous_available_seasons"] = list(previous_seasons)
        new_metadata.extra["newly_added_seasons"] = list(added_seasons)
        self._write_metadata(destination, new_metadata)

        if added_seasons:
            logger.info("Update detected new season(s): %s", ", ".join(added_seasons))
        else:
            logger.info("Update completed; no new seasons detected.")

        return new_metadata

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _download_zip(self, zip_path: Path) -> str:
        """Download the repository archive, trying each candidate branch.

        Args:
            zip_path: Local path the archive should be written to.

        Returns:
            str: The branch name that succeeded.

        Raises:
            DataSourceError: If no candidate branch could be downloaded.
        """
        codeload_base = self._repo_url.replace("github.com", "codeload.github.com")
        last_error: Exception | None = None

        for branch in _CANDIDATE_BRANCHES:
            url = f"{codeload_base}/zip/refs/heads/{branch}"
            try:
                self._stream_download(url, zip_path)
                return branch
            except (requests.RequestException, DataSourceError) as exc:
                last_error = exc
                logger.debug("Branch '%s' unavailable at %s: %s", branch, url, exc)

        raise DataSourceError(
            f"Could not download {self._repo_url} on any of {_CANDIDATE_BRANCHES}: "
            f"{last_error}"
        )

    def _stream_download(self, url: str, destination: Path) -> None:
        """Stream a URL's contents to disk, with retry on transient failures.

        Args:
            url: URL to fetch.
            destination: Local file path to write the response body to.

        Raises:
            DataSourceError: If the response status indicates failure.
        """

        @retry(
            max_attempts=self._max_retries,
            delay_seconds=2.0,
            exceptions=(requests.ConnectionError, requests.Timeout),
        )
        def _do_download() -> None:
            with requests.get(url, stream=True, timeout=self._timeout_seconds) as response:
                if response.status_code != 200:
                    raise DataSourceError(
                        f"Unexpected status {response.status_code} fetching {url}."
                    )
                with open(destination, "wb") as fh:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        fh.write(chunk)

        _do_download()

    @staticmethod
    def _find_extracted_repo_root(extraction_dir: Path) -> Path:
        """Locate the single top-level directory produced by extraction.

        Args:
            extraction_dir: Directory the archive was extracted into.

        Returns:
            Path: The repository's root directory
            (e.g. ``Fantasy-Premier-League-master``).

        Raises:
            DataSourceError: If the expected single subdirectory is not
                found.
        """
        candidates = [p for p in extraction_dir.iterdir() if p.is_dir()]
        if len(candidates) != 1:
            raise DataSourceError(
                f"Expected exactly one top-level directory after extraction, "
                f"found {len(candidates)} in {extraction_dir}."
            )
        return candidates[0]

    def _load_season(self, season_dir: Path, season: str) -> pd.DataFrame | None:
        """Load a single season's merged Gameweek data.

        Args:
            season_dir: Directory for a single season
                (``data/<season>``).
            season: The season identifier, added as a column.

        Returns:
            pd.DataFrame | None: The season's data, or ``None`` if no
            usable file was found.
        """
        merged_path = season_dir / _GWS_SUBDIR / _MERGED_GW_FILENAME
        if not merged_path.exists():
            logger.warning(
                "No %s found for season %s at %s; skipping season.",
                _MERGED_GW_FILENAME,
                season,
                merged_path,
            )
            return None

        try:
            frame = read_csv_robust(merged_path, low_memory=False)
        except (OSError, pd.errors.ParserError, UnicodeDecodeError) as exc:
            logger.warning("Failed to read %s: %s", merged_path, exc)
            return None

        frame["season"] = season
        return frame

    @staticmethod
    def _write_metadata(destination: Path, metadata: DataSourceMetadata) -> None:
        """Persist metadata to disk so subsequent ``update()`` calls can diff it.

        Args:
            destination: Directory the metadata file should live in.
            metadata: Metadata to serialize.
        """
        payload = asdict(metadata)
        payload["retrieved_at"] = (
            metadata.retrieved_at.isoformat() if metadata.retrieved_at else None
        )
        (destination / _METADATA_FILENAME).write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _read_metadata(destination: Path) -> dict[str, Any] | None:
        """Read previously persisted metadata, if any.

        Args:
            destination: Directory the metadata file may live in.

        Returns:
            dict[str, Any] | None: The parsed metadata, or ``None`` if
            no metadata file exists yet.
        """
        metadata_path = destination / _METADATA_FILENAME
        if not metadata_path.exists():
            return None
        try:
            return json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read existing metadata at %s: %s", metadata_path, exc)
            return None
