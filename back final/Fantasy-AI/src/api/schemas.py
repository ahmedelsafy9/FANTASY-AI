"""Pydantic response models for the Fantasy-AI API.

Fields are intentionally optional (``| None``) wherever the underlying
column might legitimately be absent for a given season or data source
— the same schema-drift tolerance the rest of the codebase applies to
raw data is applied here to API responses, rather than raising a
validation error for a merely-missing optional stat.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PlayerResponse(BaseModel):
    """A player's most recently known state."""

    data: dict[str, Any] = Field(
        description="The player's latest known row: identity, raw stats, and engineered features."
    )


class PredictionListResponse(BaseModel):
    """A list of next-Gameweek predictions."""

    count: int = Field(description="Number of predictions returned.")
    predicted_for_gw_note: str = Field(
        description="Reminder that each player's predicted_for_gw may differ slightly "
        "depending on how many matches they've played."
    )
    predictions: list[dict[str, Any]] = Field(description="Predictions, sorted highest to lowest.")


class CaptainResponse(BaseModel):
    """A captain pick recommendation."""

    recommendation: dict[str, Any] = Field(description="The recommended player's full row.")
    reasoning: str = Field(description="Why this player was recommended.")
    pool_size: int = Field(description="How many players were considered for this pick.")


class HealthResponse(BaseModel):
    """API health/readiness status."""

    status: str
    model_name: str | None = None
    player_count: int | None = None
    live_metadata_available: bool | None = None
