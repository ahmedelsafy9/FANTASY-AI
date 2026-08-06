"""Unit tests for src.common.season_utils."""

from __future__ import annotations

from pathlib import Path

from src.common.season_utils import detect_seasons, filter_requested_seasons, is_valid_season


def test_is_valid_season_accepts_correct_format() -> None:
    """A well-formed YYYY-YY season string must be accepted."""
    assert is_valid_season("2022-23") is True
    assert is_valid_season("1999-00") is True


def test_is_valid_season_rejects_malformed_strings() -> None:
    """Malformed season-like strings must be rejected."""
    assert is_valid_season("gws") is False
    assert is_valid_season("2022_23") is False
    assert is_valid_season("22-23") is False
    assert is_valid_season("") is False


def test_detect_seasons_returns_empty_tuple_for_missing_directory(tmp_path: Path) -> None:
    """detect_seasons must handle a nonexistent data root gracefully."""
    assert detect_seasons(tmp_path / "missing") == ()


def test_detect_seasons_finds_and_sorts_season_directories(tmp_path: Path) -> None:
    """detect_seasons must find only valid season dirs, sorted ascending."""
    (tmp_path / "2023-24").mkdir()
    (tmp_path / "2021-22").mkdir()
    (tmp_path / "2022-23").mkdir()
    (tmp_path / "docs").mkdir()  # not a season, must be excluded
    (tmp_path / "readme.md").write_text("x")  # a file, not a dir

    result = detect_seasons(tmp_path)

    assert result == ("2021-22", "2022-23", "2023-24")


def test_filter_requested_seasons_returns_all_when_empty() -> None:
    """An empty request tuple must mean 'use all available seasons'."""
    available = ("2021-22", "2022-23", "2023-24")
    assert filter_requested_seasons(available, ()) == available


def test_filter_requested_seasons_restricts_to_intersection() -> None:
    """A non-empty request must restrict to the intersection, preserving order."""
    available = ("2021-22", "2022-23", "2023-24")
    requested = ("2023-24", "2021-22", "1999-00")
    assert filter_requested_seasons(available, requested) == ("2021-22", "2023-24")
