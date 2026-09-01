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


def test_atomic_write_csv_writes_and_replaces(tmp_path: Path) -> None:
    """atomic_write_csv must write a DataFrame and safely replace existing files."""
    import pandas as pd
    from src.common.file_utils import atomic_write_csv

    target = tmp_path / "test.csv"
    df1 = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    result = atomic_write_csv(df1, target)

    assert result == target
    assert target.exists()
    read_df = pd.read_csv(target)
    assert len(read_df) == 2
    assert list(read_df.columns) == ["a", "b"]

    # Overwrite atomically
    df2 = pd.DataFrame({"a": [10, 20, 30], "b": [40, 50, 60]})
    atomic_write_csv(df2, target)
    read_df2 = pd.read_csv(target)
    assert len(read_df2) == 3
    assert read_df2.iloc[0]["a"] == 10


def test_validate_dataset_file_valid_csv(tmp_path: Path) -> None:
    """validate_dataset_file returns the row count for a valid non-empty CSV."""
    from src.common.file_utils import validate_dataset_file

    path = tmp_path / "valid.csv"
    path.write_text("col1,col2\nval1,val2\nval3,val4\n", encoding="utf-8")

    rows = validate_dataset_file(path)
    assert rows == 2


def test_validate_dataset_file_missing_raises(tmp_path: Path) -> None:
    """validate_dataset_file raises DataValidationError if the file is missing."""
    import pytest
    from src.common.file_utils import validate_dataset_file
    from src.core.exceptions import DataValidationError

    path = tmp_path / "nonexistent.csv"
    with pytest.raises(DataValidationError, match="does not exist"):
        validate_dataset_file(path)


def test_validate_dataset_file_zero_bytes_raises(tmp_path: Path) -> None:
    """validate_dataset_file raises DataValidationError on a 0-byte file."""
    import pytest
    from src.common.file_utils import validate_dataset_file
    from src.core.exceptions import DataValidationError

    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")

    with pytest.raises(DataValidationError, match="empty \\(0 bytes\\)"):
        validate_dataset_file(path)


def test_validate_dataset_file_header_only_raises(tmp_path: Path) -> None:
    """validate_dataset_file raises DataValidationError on a CSV with 0 data rows."""
    import pytest
    from src.common.file_utils import validate_dataset_file
    from src.core.exceptions import DataValidationError

    path = tmp_path / "header_only.csv"
    path.write_text("col1,col2\n", encoding="utf-8")

    with pytest.raises(DataValidationError, match="0 data rows"):
        validate_dataset_file(path)


def test_validate_dataset_file_directory_raises(tmp_path: Path) -> None:
    """validate_dataset_file raises DataValidationError if path is a directory."""
    import pytest
    from src.common.file_utils import validate_dataset_file
    from src.core.exceptions import DataValidationError

    dir_path = tmp_path / "some_dir"
    dir_path.mkdir()

    with pytest.raises(DataValidationError, match="not a regular file"):
        validate_dataset_file(dir_path)
