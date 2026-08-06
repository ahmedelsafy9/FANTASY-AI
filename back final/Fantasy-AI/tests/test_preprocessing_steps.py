"""Unit tests for individual preprocessing steps."""

from __future__ import annotations

import pandas as pd

from src.preprocessing.steps.convert_types import ConvertTypesStep
from src.preprocessing.steps.dedupe import DropDuplicatesStep
from src.preprocessing.steps.drop_invalid_required import DropInvalidRequiredRowsStep
from src.preprocessing.steps.fill_missing import FillMissingValuesStep
from src.preprocessing.steps.normalize_names import NormalizeNamesStep


# --- DropDuplicatesStep -------------------------------------------------------


def test_drop_duplicates_removes_full_duplicate_rows() -> None:
    """Fully identical rows must be reduced to a single row."""
    df = pd.DataFrame({"season": ["2022-23", "2022-23"], "name": ["A", "A"], "GW": [1, 1]})
    step = DropDuplicatesStep(key_columns=("season", "name", "GW"))
    result, summary = step.apply(df)
    assert len(result) == 1
    assert summary.rows_before == 2
    assert summary.rows_after == 1


def test_drop_duplicates_removes_key_duplicates_keeping_first() -> None:
    """Duplicate logical keys must be reduced to the first occurrence."""
    df = pd.DataFrame(
        {
            "season": ["2022-23", "2022-23"],
            "name": ["A", "A"],
            "GW": [1, 1],
            "minutes": [90, 45],
        }
    )
    step = DropDuplicatesStep(key_columns=("season", "name", "GW"))
    result, _ = step.apply(df)
    assert len(result) == 1
    assert result.iloc[0]["minutes"] == 90


def test_drop_duplicates_preserves_unique_rows() -> None:
    """Rows with no duplication must all be kept."""
    df = pd.DataFrame({"season": ["2022-23", "2022-23"], "name": ["A", "B"], "GW": [1, 1]})
    step = DropDuplicatesStep(key_columns=("season", "name", "GW"))
    result, _ = step.apply(df)
    assert len(result) == 2


# --- DropInvalidRequiredRowsStep ----------------------------------------------


def test_drop_invalid_required_rows_removes_rows_missing_required_values() -> None:
    """A row missing any required column value must be dropped."""
    df = pd.DataFrame({"season": ["2022-23", None], "name": ["A", "B"]})
    step = DropInvalidRequiredRowsStep(required_columns=("season", "name"))
    result, summary = step.apply(df)
    assert len(result) == 1
    assert summary.rows_after == 1


def test_drop_invalid_required_rows_keeps_complete_rows() -> None:
    """Rows with all required values present must be kept unchanged."""
    df = pd.DataFrame({"season": ["2022-23", "2023-24"], "name": ["A", "B"]})
    step = DropInvalidRequiredRowsStep(required_columns=("season", "name"))
    result, _ = step.apply(df)
    assert len(result) == 2


def test_drop_invalid_required_rows_ignores_absent_required_columns() -> None:
    """A required column absent from the data must not raise an error."""
    df = pd.DataFrame({"season": ["2022-23"]})
    step = DropInvalidRequiredRowsStep(required_columns=("season", "not_present"))
    result, _ = step.apply(df)
    assert len(result) == 1


# --- NormalizeNamesStep --------------------------------------------------------


def test_normalize_names_strips_and_collapses_whitespace() -> None:
    """Leading/trailing/internal extra whitespace must be normalized."""
    df = pd.DataFrame({"name": ["  Mohamed   Salah  "]})
    step = NormalizeNamesStep(name_columns=("name",))
    result, _ = step.apply(df)
    assert result.iloc[0]["name"] == "Mohamed Salah"


def test_normalize_names_adds_ascii_folded_join_key() -> None:
    """A companion '<col>_normalized' column must be added with accents removed."""
    df = pd.DataFrame({"name": ["Martin Ødegaard"]})
    step = NormalizeNamesStep(name_columns=("name",))
    result, _ = step.apply(df)
    assert "name_normalized" in result.columns
    assert result.iloc[0]["name_normalized"] == "martin odegaard"


def test_normalize_names_handles_missing_values_gracefully() -> None:
    """A missing name value must be left as-is, not raise an error."""
    df = pd.DataFrame({"name": [None, "Kane"]})
    step = NormalizeNamesStep(name_columns=("name",))
    result, _ = step.apply(df)
    assert pd.isna(result.iloc[0]["name"])
    assert pd.isna(result.iloc[0]["name_normalized"])


# --- ConvertTypesStep -----------------------------------------------------------


def test_convert_types_casts_integer_columns_to_nullable_int() -> None:
    """Integer columns must become pandas nullable Int64, tolerating missing values."""
    df = pd.DataFrame({"GW": ["1", "2", None]})
    step = ConvertTypesStep(
        integer_columns=("GW",), float_columns=(), boolean_columns=(), datetime_columns=()
    )
    result, _ = step.apply(df)
    assert str(result["GW"].dtype) == "Int64"
    assert result["GW"].iloc[2] is pd.NA


def test_convert_types_casts_float_columns() -> None:
    """Float columns must be coerced to float64."""
    df = pd.DataFrame({"ict_index": ["1.5", "2.75"]})
    step = ConvertTypesStep(
        integer_columns=(), float_columns=("ict_index",), boolean_columns=(), datetime_columns=()
    )
    result, _ = step.apply(df)
    assert result["ict_index"].dtype == "float64"
    assert result["ict_index"].iloc[0] == 1.5


def test_convert_types_casts_boolean_columns() -> None:
    """Boolean-like string values must be coerced to a proper boolean dtype."""
    df = pd.DataFrame({"was_home": ["True", "False", "yes", "no"]})
    step = ConvertTypesStep(
        integer_columns=(), float_columns=(), boolean_columns=("was_home",), datetime_columns=()
    )
    result, _ = step.apply(df)
    assert str(result["was_home"].dtype) == "boolean"
    assert list(result["was_home"]) == [True, False, True, False]


def test_convert_types_casts_datetime_columns() -> None:
    """Datetime-like string values must be parsed into timestamps."""
    df = pd.DataFrame({"kickoff_time": ["2022-08-06T14:00:00Z"]})
    step = ConvertTypesStep(
        integer_columns=(), float_columns=(), boolean_columns=(), datetime_columns=("kickoff_time",)
    )
    result, _ = step.apply(df)
    assert pd.api.types.is_datetime64_any_dtype(result["kickoff_time"])


# --- FillMissingValuesStep -----------------------------------------------------


def test_fill_missing_values_fills_configured_columns_with_zero() -> None:
    """Missing values in zero-fill columns must be replaced with 0."""
    df = pd.DataFrame({"bonus": [1, None, 3]})
    step = FillMissingValuesStep(zero_fill_columns=("bonus",))
    result, summary = step.apply(df)
    assert result["bonus"].tolist() == [1, 0, 3]
    assert "bonus" in summary.description


def test_fill_missing_values_ignores_columns_without_missing_data() -> None:
    """A column with no missing values must be left untouched and unreported."""
    df = pd.DataFrame({"bonus": [1, 2, 3]})
    step = FillMissingValuesStep(zero_fill_columns=("bonus",))
    result, summary = step.apply(df)
    assert result["bonus"].tolist() == [1, 2, 3]
    assert "{}" in summary.description


def test_fill_missing_values_leaves_unconfigured_columns_untouched() -> None:
    """A column not in zero_fill_columns must retain its missing values."""
    df = pd.DataFrame({"value": [1, None, 3]})
    step = FillMissingValuesStep(zero_fill_columns=("bonus",))
    result, _ = step.apply(df)
    assert pd.isna(result["value"].iloc[1])
