"""Reusable filesystem utilities built on :mod:`pathlib`.

These helpers centralize common filesystem operations (directory
creation, safe writes, listing files by extension) so the rest of the
codebase never touches :mod:`os` directly, keeping path handling
consistent and testable.
"""

from __future__ import annotations

import os
import shutil
import uuid
import zipfile
from pathlib import Path

import pandas as pd

from src.config.logging_config import get_logger
from src.core.exceptions import DataValidationError

logger = get_logger(__name__)

_CSV_ENCODING_CANDIDATES: tuple[str, ...] = ("utf-8", "cp1252", "latin-1")


def atomic_write_csv(df: pd.DataFrame, path: Path, **to_csv_kwargs: object) -> Path:
    """Atomically write a DataFrame to CSV via a temp file in the same directory.

    Guarantees that readers never see a partially written, truncated, or 0-byte
    file if writing is in progress or fails mid-stream.

    Args:
        df: DataFrame to write.
        path: Target file path.
        **to_csv_kwargs: Additional keyword arguments forwarded to
            :meth:`pandas.DataFrame.to_csv`. Defaults to ``index=False``.

    Returns:
        Path: The target path written.
    """
    ensure_directory(path.parent)
    if "index" not in to_csv_kwargs:
        to_csv_kwargs["index"] = False

    unique_suffix = f".tmp.{os.getpid()}.{uuid.uuid4().hex}"
    temp_path = path.parent / f"{path.name}{unique_suffix}"

    try:
        df.to_csv(temp_path, **to_csv_kwargs)  # type: ignore[arg-type]
        if not temp_path.exists() or temp_path.stat().st_size == 0:
            raise DataValidationError(
                f"Failed to write CSV: temporary file {temp_path} is empty or missing"
            )
        os.replace(temp_path, path)
    except Exception:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise
    return path


def validate_dataset_file(path: Path) -> int:
    """Defensively validate that a dataset CSV exists, is non-empty, and has data rows.

    Args:
        path: Path to the CSV file to validate.

    Returns:
        int: The number of data rows in the CSV file.

    Raises:
        DataValidationError: If the file does not exist, is empty, lacks a valid
            header, or contains 0 data rows.
    """
    if not path.exists():
        raise DataValidationError(f"Dataset file does not exist: {path}")

    if not path.is_file():
        raise DataValidationError(f"Dataset path is not a regular file: {path}")

    size = path.stat().st_size
    if size == 0:
        raise DataValidationError(
            f"Dataset file is empty (0 bytes): {path}. "
            "The file may be corrupted, truncated, or incomplete."
        )

    try:
        header_df = pd.read_csv(path, nrows=0)
        if header_df.columns.empty or len(header_df.columns) == 0:
            raise DataValidationError(f"Dataset CSV at {path} contains no header columns.")
    except pd.errors.EmptyDataError as exc:
        raise DataValidationError(
            f"Dataset CSV at {path} is empty or has no columns to parse."
        ) from exc
    except Exception as exc:
        if isinstance(exc, DataValidationError):
            raise
        raise DataValidationError(
            f"Failed to parse CSV header from dataset at {path}: {exc}"
        ) from exc

    try:
        first_col = header_df.columns[0]
        row_count = len(pd.read_csv(path, usecols=[first_col], low_memory=False))
        if row_count <= 0:
            raise DataValidationError(
                f"Dataset CSV at {path} contains a header but 0 data rows."
            )
        return row_count
    except pd.errors.EmptyDataError as exc:
        raise DataValidationError(
            f"Dataset CSV at {path} contains 0 data rows."
        ) from exc
    except Exception as exc:
        if isinstance(exc, DataValidationError):
            raise
        raise DataValidationError(
            f"Failed to count rows in dataset at {path}: {exc}"
        ) from exc


def ensure_directory(path: Path) -> Path:
    """Ensure a directory exists, creating parents as needed.

    Args:
        path: Directory path to create if missing.

    Returns:
        Path: The same path, guaranteed to exist as a directory.
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_files(directory: Path, pattern: str = "*") -> list[Path]:
    """List files in a directory matching a glob pattern.

    Args:
        directory: Directory to search.
        pattern: Glob pattern to match, e.g. ``"*.csv"``.

    Returns:
        list[Path]: Sorted list of matching file paths. Empty if the
        directory does not exist.
    """
    if not directory.exists():
        logger.debug("Directory %s does not exist; returning empty list.", directory)
        return []
    return sorted(p for p in directory.glob(pattern) if p.is_file())


def is_empty_directory(directory: Path) -> bool:
    """Check whether a directory is missing or has no entries.

    Args:
        directory: Directory to check.

    Returns:
        bool: ``True`` if the directory does not exist or contains no
        files or subdirectories.
    """
    if not directory.exists():
        return True
    return not any(directory.iterdir())


def safe_filename(name: str) -> str:
    """Sanitize a string so it can be safely used as a filename.

    Args:
        name: Raw candidate filename.

    Returns:
        str: A filesystem-safe filename with disallowed characters
        replaced by underscores.
    """
    disallowed = '<>:"/\\|?*'
    sanitized = "".join("_" if ch in disallowed else ch for ch in name.strip())
    return sanitized or "unnamed"


def extract_zip(zip_path: Path, destination: Path) -> Path:
    """Extract a zip archive into ``destination``.

    Args:
        zip_path: Path to the ``.zip`` file to extract.
        destination: Directory to extract the archive into. Created if
            it does not already exist.

    Returns:
        Path: The ``destination`` directory.
    """
    ensure_directory(destination)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(destination)
    return destination


def replace_directory(source: Path, destination: Path) -> Path:
    """Atomically-ish replace ``destination`` with the contents of ``source``.

    Any existing content at ``destination`` is removed first.

    Args:
        source: Directory whose contents should become ``destination``.
        destination: Target directory to (re)create.

    Returns:
        Path: The ``destination`` directory.
    """
    if destination.exists():
        shutil.rmtree(destination)
    shutil.move(str(source), str(destination))
    return destination


def read_csv_robust(path: Path, **read_csv_kwargs: object) -> pd.DataFrame:
    """Read a CSV file, retrying with alternate encodings on failure.

    Some historical FPL data files are not strictly UTF-8 encoded
    (e.g. accented characters in player or team names). This helper
    tries a small set of common encodings before giving up.

    Args:
        path: CSV file to read.
        **read_csv_kwargs: Additional keyword arguments forwarded to
            :func:`pandas.read_csv` (an explicit ``encoding`` is
            ignored, since encodings are tried automatically).

    Returns:
        pd.DataFrame: The parsed CSV contents.

    Raises:
        UnicodeDecodeError: If none of the candidate encodings succeed.
    """
    read_csv_kwargs.pop("encoding", None)
    last_error: UnicodeDecodeError | None = None
    for encoding in _CSV_ENCODING_CANDIDATES:
        try:
            return pd.read_csv(path, encoding=encoding, **read_csv_kwargs)  # type: ignore[arg-type]
        except UnicodeDecodeError as exc:
            last_error = exc
            logger.debug("Encoding %s failed for %s: %s", encoding, path, exc)
    assert last_error is not None
    raise last_error
