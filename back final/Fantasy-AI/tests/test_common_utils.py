"""Unit tests for src.common utility modules."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from src.common.decorators import retry, timed
from src.common.file_utils import (
    ensure_directory,
    is_empty_directory,
    list_files,
    safe_filename,
)


# --- file_utils -------------------------------------------------------------


def test_ensure_directory_creates_nested_path(tmp_path: Path) -> None:
    """ensure_directory should create arbitrarily nested directories."""
    target = tmp_path / "a" / "b" / "c"
    result = ensure_directory(target)
    assert result.exists()
    assert result.is_dir()


def test_list_files_returns_empty_list_for_missing_directory(tmp_path: Path) -> None:
    """list_files must gracefully handle a directory that does not exist."""
    missing = tmp_path / "does_not_exist"
    assert list_files(missing) == []


def test_list_files_filters_by_pattern(tmp_path: Path) -> None:
    """list_files must only return files matching the glob pattern."""
    (tmp_path / "a.csv").write_text("x")
    (tmp_path / "b.txt").write_text("x")
    (tmp_path / "c.csv").write_text("x")

    result = list_files(tmp_path, "*.csv")

    assert [p.name for p in result] == ["a.csv", "c.csv"]


def test_is_empty_directory_true_for_missing_directory(tmp_path: Path) -> None:
    """A nonexistent directory must be reported as empty."""
    assert is_empty_directory(tmp_path / "missing") is True


def test_is_empty_directory_false_when_containing_files(tmp_path: Path) -> None:
    """A directory containing at least one entry is not empty."""
    (tmp_path / "file.txt").write_text("data")
    assert is_empty_directory(tmp_path) is False


def test_safe_filename_replaces_disallowed_characters() -> None:
    """safe_filename must strip characters that are unsafe on common filesystems."""
    assert safe_filename('a:b/c*d?.csv') == "a_b_c_d_.csv"


def test_safe_filename_returns_placeholder_for_empty_input() -> None:
    """An empty or whitespace-only name should fall back to a placeholder."""
    assert safe_filename("   ") == "unnamed"


# --- decorators ---------------------------------------------------------------


def test_retry_succeeds_after_transient_failures() -> None:
    """retry() should retry until the function succeeds within max_attempts."""
    calls = {"count": 0}

    @retry(max_attempts=3, delay_seconds=0.01, exceptions=(ValueError,))
    def flaky() -> str:
        calls["count"] += 1
        if calls["count"] < 2:
            raise ValueError("transient failure")
        return "ok"

    assert flaky() == "ok"
    assert calls["count"] == 2


def test_retry_raises_after_exhausting_attempts() -> None:
    """retry() should re-raise the last exception once attempts are exhausted."""
    calls = {"count": 0}

    @retry(max_attempts=2, delay_seconds=0.01, exceptions=(ValueError,))
    def always_fails() -> None:
        calls["count"] += 1
        raise ValueError("permanent failure")

    with pytest.raises(ValueError):
        always_fails()
    assert calls["count"] == 2


def test_retry_does_not_catch_unlisted_exceptions() -> None:
    """retry() must let exceptions outside `exceptions` propagate immediately."""

    @retry(max_attempts=3, delay_seconds=0.01, exceptions=(ValueError,))
    def raises_type_error() -> None:
        raise TypeError("not retried")

    with pytest.raises(TypeError):
        raises_type_error()


def test_timed_returns_original_result() -> None:
    """timed() must not alter the wrapped function's return value."""

    @timed
    def add(a: int, b: int) -> int:
        time.sleep(0.01)
        return a + b

    assert add(2, 3) == 5
