"""Domain models shared by feature engineering steps and the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd


@dataclass(frozen=True)
class RollingFeatureSpec:
    """Specification for one rolling-window feature to derive.

    Attributes:
        output_name: Base name used to build output columns, e.g.
            ``"xG"`` produces ``xG_avg_last_3``, ``xG_avg_last_5``, ...
        source_candidates: Candidate source column names, in priority
            order. The first one present in the data is used — this
            lets the same spec gracefully handle schema drift across
            seasons (e.g. ``expected_goals`` vs ``xG``).
        windows: Window sizes (in matches) to compute a rolling
            average over.
    """

    output_name: str
    source_candidates: tuple[str, ...]
    windows: tuple[int, ...]


@dataclass
class FeatureStepSummary:
    """A record of what a single feature engineering step did.

    Attributes:
        step_name: Identifier of the step that produced this summary.
        rows_before: Row count before the step ran.
        rows_after: Row count after the step ran (feature steps never
            remove rows, so this should equal ``rows_before``).
        columns_added: Names of the columns this step added.
        description: Human-readable note on what happened.
    """

    step_name: str
    rows_before: int
    rows_after: int
    columns_added: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class FeaturePipelineResult:
    """The outcome of running a full feature engineering pipeline.

    Attributes:
        data: The engineered DataFrame.
        generated_at: When the pipeline finished running.
        rows_before: Row count before any step ran.
        rows_after: Row count after every step ran.
        step_summaries: One :class:`FeatureStepSummary` per step, in
            order.
    """

    data: pd.DataFrame = field(repr=False)
    generated_at: datetime
    rows_before: int
    rows_after: int
    step_summaries: list[FeatureStepSummary] = field(default_factory=list)
