"""Unit tests for PreprocessingPipeline, the default-steps factory, and the summary writer."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.config.settings import PreprocessingSettings, ValidationSettings
from src.preprocessing.factory import build_default_pipeline_steps
from src.preprocessing.pipeline import PreprocessingPipeline
from src.preprocessing.steps.base import PreprocessingStep, StepSummary
from src.preprocessing.summary_writer import write_summary


class _AddColumnStep(PreprocessingStep):
    @property
    def name(self) -> str:
        return "add_column"

    def apply(self, data: pd.DataFrame) -> tuple[pd.DataFrame, StepSummary]:
        result = data.copy()
        result["added"] = 1
        return result, StepSummary(
            step_name=self.name,
            rows_before=len(data),
            rows_after=len(result),
            description="added a column",
        )


class _DropFirstRowStep(PreprocessingStep):
    @property
    def name(self) -> str:
        return "drop_first_row"

    def apply(self, data: pd.DataFrame) -> tuple[pd.DataFrame, StepSummary]:
        result = data.iloc[1:].reset_index(drop=True)
        return result, StepSummary(
            step_name=self.name,
            rows_before=len(data),
            rows_after=len(result),
            description="dropped first row",
        )


def test_pipeline_runs_steps_in_order_and_threads_data() -> None:
    """Each step's output must become the next step's input."""
    pipeline = PreprocessingPipeline(steps=[_DropFirstRowStep(), _AddColumnStep()])
    df = pd.DataFrame({"x": [1, 2, 3]})
    result = pipeline.run(df)

    assert result.rows_before == 3
    assert result.rows_after == 2
    assert "added" in result.data.columns
    assert len(result.step_summaries) == 2


def test_pipeline_result_preserves_step_summary_order() -> None:
    """Step summaries must appear in the same order the steps were run."""
    pipeline = PreprocessingPipeline(steps=[_DropFirstRowStep(), _AddColumnStep()])
    result = pipeline.run(pd.DataFrame({"x": [1, 2]}))
    assert [s.step_name for s in result.step_summaries] == ["drop_first_row", "add_column"]


def test_build_default_pipeline_steps_returns_five_steps() -> None:
    """The factory must build the full standard step sequence."""
    steps = build_default_pipeline_steps(PreprocessingSettings(), ValidationSettings())
    names = [step.name for step in steps]
    assert names == [
        "normalize_names",
        "drop_duplicates",
        "drop_invalid_required_rows",
        "convert_types",
        "fill_missing_values",
    ]


def test_default_pipeline_cleans_a_realistic_dirty_dataset() -> None:
    """End-to-end: the default pipeline must clean a deliberately messy dataset."""
    df = pd.DataFrame(
        {
            "season": ["2022-23", "2022-23", "2022-23", None],
            "name": ["  Mohamed   Salah  ", "Mohamed Salah", "Erling Haaland", "Kane"],
            "GW": ["1", "1", "2", "3"],
            "total_points": ["10", "10", "9", "8"],
            "bonus": [1, 1, None, 2],
            "was_home": ["True", "True", "False", "yes"],
        }
    )
    preprocessing_settings = PreprocessingSettings(
        name_columns=("name",),
        boolean_columns=("was_home",),
        datetime_columns=(),
        integer_columns=("GW", "total_points"),
        float_columns=(),
        zero_fill_columns=("bonus",),
    )
    validation_settings = ValidationSettings(
        required_columns=("season", "name"),
        duplicate_key_columns=("season", "name", "GW"),
    )
    steps = build_default_pipeline_steps(preprocessing_settings, validation_settings)
    pipeline = PreprocessingPipeline(steps=steps)
    result = pipeline.run(df)

    cleaned = result.data
    # The row with missing season must be dropped.
    assert cleaned["season"].isna().sum() == 0
    # The exact duplicate (same season/name/GW) must be reduced to one row.
    assert len(cleaned) == 2
    # Name normalization must have collapsed whitespace.
    assert cleaned.iloc[0]["name"] == "Mohamed Salah"
    # Types must be converted.
    assert str(cleaned["GW"].dtype) == "Int64"
    assert str(cleaned["was_home"].dtype) == "boolean"
    # Missing bonus values must be filled with 0, where still present.
    assert cleaned["bonus"].isna().sum() == 0


def test_write_summary_produces_valid_json(tmp_path: Path) -> None:
    """write_summary must produce a JSON file describing the pipeline run."""
    pipeline = PreprocessingPipeline(steps=[_AddColumnStep()])
    result = pipeline.run(pd.DataFrame({"x": [1, 2, 3]}))

    summary_path = tmp_path / "summary.json"
    write_summary(result, summary_path)

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["rows_before"] == 3
    assert payload["rows_after"] == 3
    assert payload["steps"][0]["step_name"] == "add_column"
