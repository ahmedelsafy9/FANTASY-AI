"""Unit tests for the newer src.common.file_utils helpers."""

from __future__ import annotations

import zipfile
from pathlib import Path

from src.common.file_utils import extract_zip, read_csv_robust, replace_directory


def test_extract_zip_extracts_all_members(tmp_path: Path) -> None:
    """extract_zip must extract every file in the archive."""
    zip_path = tmp_path / "archive.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("folder/file1.txt", "hello")
        zf.writestr("folder/nested/file2.txt", "world")

    destination = tmp_path / "out"
    result = extract_zip(zip_path, destination)

    assert result == destination
    assert (destination / "folder" / "file1.txt").read_text() == "hello"
    assert (destination / "folder" / "nested" / "file2.txt").read_text() == "world"


def test_replace_directory_moves_and_overwrites(tmp_path: Path) -> None:
    """replace_directory must move source contents in and remove old destination content."""
    source = tmp_path / "source"
    source.mkdir()
    (source / "new.txt").write_text("new")

    destination = tmp_path / "destination"
    destination.mkdir()
    (destination / "old.txt").write_text("old")

    result = replace_directory(source, destination)

    assert result == destination
    assert (destination / "new.txt").exists()
    assert not (destination / "old.txt").exists()
    assert not source.exists()


def test_read_csv_robust_reads_utf8(tmp_path: Path) -> None:
    """read_csv_robust must read a standard UTF-8 CSV without issue."""
    path = tmp_path / "data.csv"
    path.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")

    df = read_csv_robust(path)

    assert list(df.columns) == ["a", "b"]
    assert len(df) == 2


def test_read_csv_robust_falls_back_to_latin1(tmp_path: Path) -> None:
    """read_csv_robust must fall back to a Latin-1-compatible encoding."""
    path = tmp_path / "data.csv"
    # 'é' encoded as cp1252/latin-1, invalid as UTF-8 on its own.
    content = "name,points\nJos\xe9,10\n"
    path.write_bytes(content.encode("cp1252"))

    df = read_csv_robust(path)

    assert list(df.columns) == ["name", "points"]
    assert df.iloc[0]["name"] == "Jos\xe9"
