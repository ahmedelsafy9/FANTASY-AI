"""Utilities for detecting and validating FPL season identifiers.

A "season" is identified by a string such as ``"2022-23"``. Centralizing
detection logic here means no module ever hardcodes a season list —
seasons are always discovered from what is actually present on disk (or
provided explicitly by the caller via configuration).
"""

from __future__ import annotations

import re
from pathlib import Path

_SEASON_PATTERN = re.compile(r"^(19|20)\d{2}-\d{2}$")


def is_valid_season(name: str) -> bool:
    """Check whether a string looks like a valid FPL season identifier.

    Args:
        name: Candidate string, e.g. a directory name.

    Returns:
        bool: ``True`` if ``name`` matches the ``YYYY-YY`` season format.
    """
    return bool(_SEASON_PATTERN.match(name))


def detect_seasons(data_root: Path) -> tuple[str, ...]:
    """Discover available seasons from subdirectories of ``data_root``.

    Args:
        data_root: Directory expected to contain one subdirectory per
            season (e.g. ``data_root / "2022-23"``).

    Returns:
        tuple[str, ...]: Sorted tuple of detected season identifiers.
        Empty if ``data_root`` does not exist or contains no matching
        subdirectories.
    """
    if not data_root.exists():
        return ()
    seasons = sorted(
        p.name for p in data_root.iterdir() if p.is_dir() and is_valid_season(p.name)
    )
    return tuple(seasons)


def filter_requested_seasons(
    available: tuple[str, ...], requested: tuple[str, ...]
) -> tuple[str, ...]:
    """Restrict the available seasons to an explicitly requested subset.

    Args:
        available: Seasons detected on disk / in the source.
        requested: Seasons explicitly requested by the caller. An empty
            tuple means "use all available seasons".

    Returns:
        tuple[str, ...]: The seasons to actually process, preserving
        the sorted order of ``available``.
    """
    if not requested:
        return available
    requested_set = set(requested)
    return tuple(season for season in available if season in requested_set)
