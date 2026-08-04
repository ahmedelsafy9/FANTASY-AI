"""Unit tests for VaastavDataSource.

All network access is mocked — no real HTTP requests are made. A fake
zip archive mimicking the real repository's layout
(``Fantasy-Premier-League-master/data/<season>/gws/merged_gw.csv``) is
built in-memory and served through a monkeypatched ``requests.get``.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from src.core.exceptions import DataSourceError, DataValidationError
from src.data_collection.sources.vaastav_source import VaastavDataSource

REPO_URL = "https://github.com/vaastav/Fantasy-Premier-League"


def _build_fake_repo_zip(seasons_data: dict[str, str]) -> bytes:
    """Build an in-memory zip mimicking the real repository layout.

    Args:
        seasons_data: Mapping of season identifier to the CSV text
            content of its ``merged_gw.csv`` file.

    Returns:
        bytes: The zip archive's raw bytes.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for season, csv_text in seasons_data.items():
            zf.writestr(
                f"Fantasy-Premier-League-master/data/{season}/gws/merged_gw.csv",
                csv_text,
            )
        # Non-season, non-data content that must be ignored.
        zf.writestr("Fantasy-Premier-League-master/README.md", "# readme")
    return buffer.getvalue()


class _FakeResponse:
    """Minimal stand-in for requests.Response used by streamed downloads."""

    def __init__(self, content: bytes, status_code: int = 200) -> None:
        self._content = content
        self.status_code = status_code

    def iter_content(self, chunk_size: int) -> Any:
        yield self._content

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


@pytest.fixture
def sample_seasons_data() -> dict[str, str]:
    """Two fake seasons of merged_gw.csv content."""
    return {
        "2021-22": (
            "name,GW,total_points,minutes\n"
            "Mohamed Salah,1,12,90\n"
            "Mohamed Salah,2,6,90\n"
        ),
        "2022-23": (
            "name,GW,total_points,minutes\n"
            "Erling Haaland,1,15,90\n"
            "Erling Haaland,2,9,80\n"
        ),
    }


def test_download_extracts_seasons_and_writes_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sample_seasons_data: dict[str, str]
) -> None:
    """download() must extract season directories and persist metadata."""
    zip_bytes = _build_fake_repo_zip(sample_seasons_data)

    def fake_get(url: str, stream: bool = False, timeout: int = 30) -> _FakeResponse:
        assert "codeload.github.com" in url
        return _FakeResponse(zip_bytes)

    monkeypatch.setattr(
        "src.data_collection.sources.vaastav_source.requests.get", fake_get
    )

    source = VaastavDataSource(repo_url=REPO_URL)
    destination = tmp_path / "vaastav"

    metadata = source.download(destination)

    assert metadata.name == "vaastav"
    assert set(metadata.extra["available_seasons"]) == {"2021-22", "2022-23"}
    assert (destination / "data" / "2021-22" / "gws" / "merged_gw.csv").exists()
    assert (destination / "_vaastav_metadata.json").exists()


def test_download_raises_when_all_branches_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """download() must raise DataSourceError when no branch responds successfully."""

    def fake_get(url: str, stream: bool = False, timeout: int = 30) -> _FakeResponse:
        return _FakeResponse(b"", status_code=404)

    monkeypatch.setattr(
        "src.data_collection.sources.vaastav_source.requests.get", fake_get
    )

    source = VaastavDataSource(repo_url=REPO_URL, max_retries=1)

    with pytest.raises(DataSourceError):
        source.download(tmp_path / "vaastav")


def test_load_merges_all_detected_seasons(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sample_seasons_data: dict[str, str]
) -> None:
    """load() must merge every detected season into one DataFrame with a season column."""
    zip_bytes = _build_fake_repo_zip(sample_seasons_data)

    def fake_get(url: str, stream: bool = False, timeout: int = 30) -> _FakeResponse:
        return _FakeResponse(zip_bytes)

    monkeypatch.setattr(
        "src.data_collection.sources.vaastav_source.requests.get", fake_get
    )

    source = VaastavDataSource(repo_url=REPO_URL)
    destination = tmp_path / "vaastav"
    source.download(destination)

    combined = source.load(destination)

    assert len(combined) == 4
    assert set(combined["season"].unique()) == {"2021-22", "2022-23"}
    assert "total_points" in combined.columns


def test_load_respects_season_filter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sample_seasons_data: dict[str, str]
) -> None:
    """load() must restrict output to explicitly requested seasons only."""
    zip_bytes = _build_fake_repo_zip(sample_seasons_data)

    def fake_get(url: str, stream: bool = False, timeout: int = 30) -> _FakeResponse:
        return _FakeResponse(zip_bytes)

    monkeypatch.setattr(
        "src.data_collection.sources.vaastav_source.requests.get", fake_get
    )

    destination = tmp_path / "vaastav"
    VaastavDataSource(repo_url=REPO_URL).download(destination)

    source = VaastavDataSource(repo_url=REPO_URL, seasons=("2022-23",))
    combined = source.load(destination)

    assert set(combined["season"].unique()) == {"2022-23"}


def test_load_raises_when_no_data_downloaded(tmp_path: Path) -> None:
    """load() must raise DataSourceError if download() was never called."""
    source = VaastavDataSource(repo_url=REPO_URL)
    with pytest.raises(DataSourceError):
        source.load(tmp_path / "never_downloaded")


def test_validate_passes_for_well_formed_data() -> None:
    """validate() must return True for a structurally sound DataFrame."""
    df = pd.DataFrame(
        {
            "season": ["2022-23", "2022-23"],
            "GW": [1, 2],
            "total_points": [10, 5],
        }
    )
    source = VaastavDataSource(repo_url=REPO_URL)
    assert source.validate(df) is True


def test_validate_raises_for_empty_dataframe() -> None:
    """validate() must raise DataValidationError for an empty DataFrame."""
    source = VaastavDataSource(repo_url=REPO_URL)
    with pytest.raises(DataValidationError):
        source.validate(pd.DataFrame())


def test_validate_raises_when_missing_required_columns() -> None:
    """validate() must raise DataValidationError when required columns are absent."""
    df = pd.DataFrame({"season": ["2022-23"]})
    source = VaastavDataSource(repo_url=REPO_URL)
    with pytest.raises(DataValidationError):
        source.validate(df)


def test_update_reports_newly_added_seasons(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sample_seasons_data: dict[str, str]
) -> None:
    """update() must detect and report seasons that are new since the last download."""
    destination = tmp_path / "vaastav"

    first_zip = _build_fake_repo_zip({"2021-22": sample_seasons_data["2021-22"]})

    def fake_get_first(url: str, stream: bool = False, timeout: int = 30) -> _FakeResponse:
        return _FakeResponse(first_zip)

    monkeypatch.setattr(
        "src.data_collection.sources.vaastav_source.requests.get", fake_get_first
    )
    VaastavDataSource(repo_url=REPO_URL).download(destination)

    full_zip = _build_fake_repo_zip(sample_seasons_data)

    def fake_get_second(url: str, stream: bool = False, timeout: int = 30) -> _FakeResponse:
        return _FakeResponse(full_zip)

    monkeypatch.setattr(
        "src.data_collection.sources.vaastav_source.requests.get", fake_get_second
    )

    source = VaastavDataSource(repo_url=REPO_URL)
    metadata = source.update(destination)

    assert metadata.extra["newly_added_seasons"] == ["2022-23"]
