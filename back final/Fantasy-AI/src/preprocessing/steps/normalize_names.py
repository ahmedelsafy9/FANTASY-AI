"""Preprocessing step that normalizes free-text name columns."""

from __future__ import annotations

import unicodedata

import pandas as pd

from src.config.logging_config import get_logger
from src.preprocessing.steps.base import PreprocessingStep, StepSummary

logger = get_logger(__name__)

# NFKD decomposition alone cannot fold these — they are distinct letters,
# not a base letter plus a combining mark — so they are mapped explicitly.
# Common in player names of Scandinavian, German, and Icelandic origin.
_EXPLICIT_CHAR_MAP = str.maketrans(
    {
        "Ø": "O",
        "ø": "o",
        "Æ": "AE",
        "æ": "ae",
        "Œ": "OE",
        "œ": "oe",
        "Đ": "D",
        "đ": "d",
        "Ł": "L",
        "ł": "l",
        "ß": "ss",
        "Ð": "D",
        "ð": "d",
        "Þ": "Th",
        "þ": "th",
    }
)


def _normalize_whitespace_and_unicode(value: object) -> object:
    """Strip, collapse whitespace, and apply Unicode NFKC normalization.

    Args:
        value: The raw cell value.

    Returns:
        object: The cleaned string, or the original value unchanged if
        it is not a string (e.g. ``NaN``).
    """
    if not isinstance(value, str):
        return value
    normalized = unicodedata.normalize("NFKC", value)
    return " ".join(normalized.split())


def _fold_to_ascii_lower(value: object) -> object:
    """Produce a diacritic-free, lowercase join key for a name.

    Useful for matching the same player across sources that spell
    accented names differently (e.g. ``"Ødegaard"`` vs ``"Odegaard"``).

    Args:
        value: The raw cell value.

    Returns:
        object: The folded string, or the original value unchanged if
        it is not a string.
    """
    if not isinstance(value, str):
        return value
    mapped = value.translate(_EXPLICIT_CHAR_MAP)
    decomposed = unicodedata.normalize("NFKD", mapped)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    return ascii_only.lower().strip()


class NormalizeNamesStep(PreprocessingStep):
    """Normalizes whitespace/Unicode in name columns and adds a join-key column.

    For each configured column, this step:

    1. Strips leading/trailing whitespace and collapses internal
       whitespace, applying Unicode NFKC normalization in place.
    2. Adds a companion ``<column>_normalized`` column containing a
       lowercase, diacritic-free version suitable for joining the same
       entity across data sources with inconsistent spelling.

    Args:
        name_columns: Columns containing free-text names to normalize.
    """

    def __init__(self, name_columns: tuple[str, ...]) -> None:
        self._name_columns = name_columns

    @property
    def name(self) -> str:
        """A short, human-readable identifier for this step."""
        return "normalize_names"

    def apply(self, data: pd.DataFrame) -> tuple[pd.DataFrame, StepSummary]:
        """Normalize each configured name column and add a join-key column.

        Args:
            data: The DataFrame to normalize.

        Returns:
            tuple[pd.DataFrame, StepSummary]: The normalized data and a
            summary of which columns were touched.
        """
        rows_before = len(data)
        cleaned = data.copy()

        touched_columns: list[str] = []
        for column in self._name_columns:
            if column not in cleaned.columns:
                continue
            cleaned[column] = cleaned[column].map(_normalize_whitespace_and_unicode)
            cleaned[f"{column}_normalized"] = cleaned[column].map(_fold_to_ascii_lower)
            touched_columns.append(column)

        summary = StepSummary(
            step_name=self.name,
            rows_before=rows_before,
            rows_after=len(cleaned),
            description=f"Normalized name column(s) {touched_columns}.",
        )
        logger.info(summary.description)
        return cleaned, summary
