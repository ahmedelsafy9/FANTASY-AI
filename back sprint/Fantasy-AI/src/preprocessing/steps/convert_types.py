"""Preprocessing step that converts columns to their proper dtypes."""

from __future__ import annotations

import pandas as pd

from src.config.logging_config import get_logger
from src.preprocessing.steps.base import PreprocessingStep, StepSummary

logger = get_logger(__name__)

_TRUE_STRINGS = {"true", "t", "1", "yes", "y"}
_FALSE_STRINGS = {"false", "f", "0", "no", "n"}


def _coerce_boolean(value: object) -> object:
    """Coerce a loosely-typed value into a proper boolean.

    Args:
        value: The raw cell value (bool, string, or number).

    Returns:
        object: ``True``/``False``, or ``pd.NA`` if the value cannot
        be confidently interpreted.
    """
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return pd.NA
    text = str(value).strip().lower()
    if text in _TRUE_STRINGS:
        return True
    if text in _FALSE_STRINGS:
        return False
    return pd.NA


class ConvertTypesStep(PreprocessingStep):
    """Converts integer, float, boolean, and datetime columns to proper dtypes.

    Uses pandas' nullable dtypes (``Int64``, ``boolean``) so that
    missing values can coexist with a proper integer/boolean dtype
    instead of silently upcasting to ``float64`` or ``object``.

    Args:
        integer_columns: Columns that should hold nullable integers.
        float_columns: Columns that should hold floats.
        boolean_columns: Columns that should hold nullable booleans.
        datetime_columns: Columns that should hold timestamps.
    """

    def __init__(
        self,
        integer_columns: tuple[str, ...],
        float_columns: tuple[str, ...],
        boolean_columns: tuple[str, ...],
        datetime_columns: tuple[str, ...],
    ) -> None:
        self._integer_columns = integer_columns
        self._float_columns = float_columns
        self._boolean_columns = boolean_columns
        self._datetime_columns = datetime_columns

    @property
    def name(self) -> str:
        """A short, human-readable identifier for this step."""
        return "convert_types"

    def apply(self, data: pd.DataFrame) -> tuple[pd.DataFrame, StepSummary]:
        """Convert each configured column group to its target dtype.

        Args:
            data: The DataFrame to convert.

        Returns:
            tuple[pd.DataFrame, StepSummary]: The converted data and a
            summary of which columns were converted.
        """
        rows_before = len(data)
        cleaned = data.copy()
        converted: list[str] = []

        for column in self._integer_columns:
            if column not in cleaned.columns:
                continue
            numeric = pd.to_numeric(cleaned[column], errors="coerce")
            non_integer_count = int(
                ((numeric.dropna() % 1) != 0).sum()
            )
            if non_integer_count:
                logger.warning(
                    "Column '%s' is configured as integer but has %d fractional "
                    "value(s); rounding to the nearest integer.",
                    column,
                    non_integer_count,
                )
            cleaned[column] = numeric.round().astype("Int64")
            converted.append(f"{column}:Int64")

        for column in self._float_columns:
            if column not in cleaned.columns:
                continue
            cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce").astype("float64")
            converted.append(f"{column}:float64")

        for column in self._boolean_columns:
            if column not in cleaned.columns:
                continue
            cleaned[column] = cleaned[column].map(_coerce_boolean).astype("boolean")
            converted.append(f"{column}:boolean")

        for column in self._datetime_columns:
            if column not in cleaned.columns:
                continue
            cleaned[column] = pd.to_datetime(cleaned[column], errors="coerce", utc=True)
            converted.append(f"{column}:datetime")

        summary = StepSummary(
            step_name=self.name,
            rows_before=rows_before,
            rows_after=len(cleaned),
            description=f"Converted {len(converted)} column(s): {converted}.",
        )
        logger.info(summary.description)
        return cleaned, summary
