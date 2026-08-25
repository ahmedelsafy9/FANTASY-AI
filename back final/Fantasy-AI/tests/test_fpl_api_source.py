"""Unit tests for FPLApiDataSource.

All network access is mocked — no real HTTP requests are made. Fake
bootstrap-static and event-live payloads are built in-memory, matching
the well-known structure of the official FPL API, and served through a
monkeypatched ``requests.get``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from src.core.exceptions import DataSourceError, DataValidationError
from src.data_collection.sources.fpl_api_source import FPLApiDataSource

BASE_URL = "https://fantasy.premierleague.com/api"


def _bootstrap_payload(finished_events: list[int], latest_deadline: str = "2023-09-16T10:00:00Z") -> dict[str, Any]:
    events = [
        {"id": i, "finished": i in finished_events, "deadline_time": latest_deadline}
        for i in range(1, 4)
    ]
    return {
        "events": events,
        "teams": [{"id": 11, "name": "Liverpool"}, {"id": 12, "name": "Everton"}],
        "elements": [
            {"id": 1, "web_name": "Salah", "team": 11, "now_cost": 130},
            {"id": 2, "web_name": "Calvert-Lewin", "team": 12, "now_cost": 75},
        ],
    }


def _live_payload() -> dict[str, Any]:
    return {
        "elements": [
            {"id": 1, "stats": {"minutes": 90, "goals_scored": 1, "total_points": 8}},
            {"id": 2, "stats": {"minutes": 60, "goals_scored": 0, "total_points": 2}},
        ]
    }


class _FakeResponse:
    """Minimal stand-in for requests.Response used by JSON GETs."""

    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, Any]:
        return self._payload


def test_download_fetches_bootstrap_and_latest_live_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """download() must fetch bootstrap-static and the latest finished event's live stats."""
    bootstrap = _bootstrap_payload(finished_events=[1, 2])
    live = _live_payload()

    def fake_get(url: str, timeout: int = 30):
        if "bootstrap-static" in url:
            return _FakeResponse(bootstrap)
        if "event/2/live" in url:
            return _FakeResponse(live)
        raise AssertionError(f"Unexpected URL requested: {url}")

    monkeypatch.setattr(
        "src.data_collection.sources.fpl_api_source.requests.get", fake_get
    )

    source = FPLApiDataSource(base_url=BASE_URL)
    destination = tmp_path / "fpl_api"
    metadata = source.download(destination)

    assert metadata.extra["latest_finished_event"] == 2
    assert metadata.records_count == 2
    assert (destination / "bootstrap_static.json").exists()
    assert (destination / "event_2_live.json").exists()


def test_download_succeeds_when_no_finished_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """download() must succeed and save bootstrap_static.json even when no Gameweek has finished yet."""
    bootstrap = _bootstrap_payload(finished_events=[])

    def fake_get(url: str, timeout: int = 30):
        if "bootstrap-static" in url:
            return _FakeResponse(bootstrap)
        raise AssertionError(f"Unexpected URL requested when no GW finished: {url}")

    monkeypatch.setattr(
        "src.data_collection.sources.fpl_api_source.requests.get", fake_get
    )

    source = FPLApiDataSource(base_url=BASE_URL)
    destination = tmp_path / "fpl_api"
    metadata = source.download(destination)

    assert metadata.extra["latest_finished_event"] is None
    assert metadata.records_count == 2
    assert (destination / "bootstrap_static.json").exists()
    assert not list(destination.glob("event_*_live.json"))


def test_download_raises_for_malformed_bootstrap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """download() must raise DataSourceError if the bootstrap response is malformed."""
    def fake_get(url: str, timeout: int = 30):
        return _FakeResponse({"unexpected_key": []})

    monkeypatch.setattr(
        "src.data_collection.sources.fpl_api_source.requests.get", fake_get
    )

    source = FPLApiDataSource(base_url=BASE_URL)
    with pytest.raises(DataSourceError, match="Malformed bootstrap-static payload"):
        source.download(tmp_path / "fpl_api")


def test_download_raises_for_network_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """download() must raise DataSourceError if the network request fails."""
    def fake_get(url: str, timeout: int = 30):
        return _FakeResponse({}, status_code=503)

    monkeypatch.setattr(
        "src.data_collection.sources.fpl_api_source.requests.get", fake_get
    )

    source = FPLApiDataSource(base_url=BASE_URL, max_retries=1)
    with pytest.raises(DataSourceError, match="Unexpected status 503"):
        source.download(tmp_path / "fpl_api")


def test_load_raises_when_no_finished_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """load() must raise DataSourceError if no Gameweek has finished yet."""
    bootstrap = _bootstrap_payload(finished_events=[])

    def fake_get(url: str, timeout: int = 30):
        return _FakeResponse(bootstrap)

    monkeypatch.setattr(
        "src.data_collection.sources.fpl_api_source.requests.get", fake_get
    )

    source = FPLApiDataSource(base_url=BASE_URL)
    destination = tmp_path / "fpl_api"
    source.download(destination)

    with pytest.raises(DataSourceError, match="No completed Gameweek found"):
        source.load(destination)


def test_load_flattens_live_stats_with_player_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """load() must merge live stats with player name/team/value from bootstrap."""
    bootstrap = _bootstrap_payload(finished_events=[1, 2])
    live = _live_payload()

    def fake_get(url: str, timeout: int = 30):
        if "bootstrap-static" in url:
            return _FakeResponse(bootstrap)
        return _FakeResponse(live)

    monkeypatch.setattr(
        "src.data_collection.sources.fpl_api_source.requests.get", fake_get
    )

    source = FPLApiDataSource(base_url=BASE_URL)
    destination = tmp_path / "fpl_api"
    source.download(destination)

    frame = source.load(destination)

    assert len(frame) == 2
    salah_row = frame[frame["element"] == 1].iloc[0]
    assert salah_row["name"] == "Salah"
    assert salah_row["team"] == "Liverpool"
    assert salah_row["value"] == 130
    assert salah_row["GW"] == 2
    assert salah_row["total_points"] == 8
    assert salah_row["season"] == "2023-24"


def test_load_raises_without_prior_download(tmp_path: Path) -> None:
    """load() must raise DataSourceError if download() was never called."""
    source = FPLApiDataSource(base_url=BASE_URL)
    with pytest.raises(DataSourceError):
        source.load(tmp_path / "never_downloaded")


def test_validate_passes_for_well_formed_data() -> None:
    """validate() must return True for a structurally sound DataFrame."""
    df = pd.DataFrame({"element": [1], "GW": [2], "season": ["2023-24"], "total_points": [8]})
    source = FPLApiDataSource(base_url=BASE_URL)
    assert source.validate(df) is True


def test_validate_raises_for_missing_columns() -> None:
    """validate() must raise DataValidationError when required columns are absent."""
    df = pd.DataFrame({"element": [1]})
    source = FPLApiDataSource(base_url=BASE_URL)
    with pytest.raises(DataValidationError):
        source.validate(df)


def test_update_detects_advanced_gameweek(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """update() must detect and report when the latest finished Gameweek advances."""
    destination = tmp_path / "fpl_api"

    bootstrap_gw1 = _bootstrap_payload(finished_events=[1])
    live = _live_payload()

    def fake_get_first(url: str, timeout: int = 30):
        if "bootstrap-static" in url:
            return _FakeResponse(bootstrap_gw1)
        return _FakeResponse(live)

    monkeypatch.setattr(
        "src.data_collection.sources.fpl_api_source.requests.get", fake_get_first
    )
    FPLApiDataSource(base_url=BASE_URL).download(destination)

    bootstrap_gw2 = _bootstrap_payload(finished_events=[1, 2])

    def fake_get_second(url: str, timeout: int = 30):
        if "bootstrap-static" in url:
            return _FakeResponse(bootstrap_gw2)
        return _FakeResponse(live)

    monkeypatch.setattr(
        "src.data_collection.sources.fpl_api_source.requests.get", fake_get_second
    )

    source = FPLApiDataSource(base_url=BASE_URL)
    metadata = source.update(destination)

    assert metadata.extra["previous_finished_event"] == 1
    assert metadata.extra["latest_finished_event"] == 2
    assert metadata.extra["advanced"] is True


def test_update_when_no_finished_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """update() must work cleanly when no Gameweek has finished yet."""
    destination = tmp_path / "fpl_api"
    bootstrap = _bootstrap_payload(finished_events=[])

    def fake_get(url: str, timeout: int = 30):
        return _FakeResponse(bootstrap)

    monkeypatch.setattr(
        "src.data_collection.sources.fpl_api_source.requests.get", fake_get
    )

    source = FPLApiDataSource(base_url=BASE_URL)
    metadata = source.update(destination)

    assert metadata.extra["latest_finished_event"] is None
    assert metadata.extra["advanced"] is False
    assert (destination / "bootstrap_static.json").exists()


def test_find_latest_finished_event_multiple_finished() -> None:
    bootstrap = {"events": [{"id": 1, "finished": True}, {"id": 4, "finished": True}, {"id": 2, "finished": False}]}
    event_id, is_provisional = FPLApiDataSource._find_latest_completed_event(bootstrap)
    assert event_id == 4
    assert is_provisional is False


def test_find_latest_finished_event_none_finished() -> None:
    bootstrap = {"events": [{"id": 1, "finished": False}, {"id": 2, "finished": False}]}
    event_id, is_provisional = FPLApiDataSource._find_latest_completed_event(bootstrap)
    assert event_id is None
    assert is_provisional is False


def test_find_latest_finished_event_malformed_bootstrap() -> None:
    with pytest.raises(DataSourceError, match="expected JSON object"):
        FPLApiDataSource._find_latest_completed_event(["not a dict"])  # type: ignore[arg-type]

    with pytest.raises(DataSourceError, match="'events' array missing"):
        FPLApiDataSource._find_latest_completed_event({"no_events": []})

    with pytest.raises(DataSourceError, match="Malformed event object"):
        FPLApiDataSource._find_latest_completed_event({"events": ["not a dict"]})


def test_find_latest_completed_event_fallback_heuristic() -> None:
    """Fallback: is_current=True + deadline in past → provisional detection."""
    bootstrap = {
        "events": [
            {
                "id": 1,
                "finished": False,
                "is_current": True,
                "deadline_time": "2020-01-01T12:00:00Z",
            },
            {
                "id": 2,
                "finished": False,
                "is_current": False,
                "deadline_time": "2099-01-01T12:00:00Z",
            },
        ]
    }
    event_id, is_provisional = FPLApiDataSource._find_latest_completed_event(bootstrap)
    assert event_id == 1
    assert is_provisional is True


def test_find_latest_completed_event_fallback_skipped_future_deadline() -> None:
    """Fallback should NOT trigger if deadline is in the future."""
    bootstrap = {
        "events": [
            {
                "id": 1,
                "finished": False,
                "is_current": True,
                "deadline_time": "2099-12-31T23:59:59Z",
            },
        ]
    }
    event_id, is_provisional = FPLApiDataSource._find_latest_completed_event(bootstrap)
    assert event_id is None
    assert is_provisional is False


def test_find_latest_completed_event_finished_takes_priority() -> None:
    """When finished=True exists, the fallback heuristic is never used."""
    bootstrap = {
        "events": [
            {
                "id": 1,
                "finished": True,
                "is_current": False,
                "deadline_time": "2020-01-01T12:00:00Z",
            },
            {
                "id": 2,
                "finished": False,
                "is_current": True,
                "deadline_time": "2020-06-01T12:00:00Z",
            },
        ]
    }
    event_id, is_provisional = FPLApiDataSource._find_latest_completed_event(bootstrap)
    assert event_id == 1
    assert is_provisional is False

