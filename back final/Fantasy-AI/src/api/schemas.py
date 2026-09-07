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
    season: str | None = Field(default=None, description="Current FPL season.")
    latest_completed_gameweek: int | None = Field(
        default=None, description="Latest completed Gameweek ingested."
    )
    predicted_gameweek: int | None = Field(
        default=None, description="Next Gameweek target being predicted."
    )
    generated_at: str | None = Field(
        default=None, description="Timestamp when predictions were generated."
    )
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
    season: str | None = None
    latest_completed_gameweek: int | None = None
    predicted_gameweek: int | None = None


class MatchPlayerImpact(BaseModel):
    """Top predicted FPL performer for a match."""

    element: int | None = None
    name: str
    position: str | None = None
    team: str
    expected_points: float | None = None
    fpl_rank_score: float | None = None
    prob_high_score_6: float | None = None
    expected_minutes: float | None = None
    photo_url: str | None = None
    value: float | None = None


class MatchPrediction(BaseModel):
    """Prediction for a single fixture using the existing Match Model."""

    fixture_id: int
    code: int | None = None
    gameweek: int
    kickoff_time: str | None = None
    home_team: str
    away_team: str
    home_team_id: int | None = None
    away_team_id: int | None = None
    home_team_logo_url: str | None = None
    away_team_logo_url: str | None = None
    home_win_probability: float
    draw_probability: float
    away_win_probability: float
    predicted_result: str = Field(description="HOME_WIN, DRAW, or AWAY_WIN")
    predicted_home_goals: float
    predicted_away_goals: float
    predicted_scoreline: str
    confidence: float
    confidence_level: str = Field(default="MODERATE", description="HIGH, MODERATE, or LOW")
    over_2_5_probability: float | None = None
    under_2_5_probability: float | None = None
    btts_probability: float | None = None
    home_clean_sheet_probability: float | None = None
    away_clean_sheet_probability: float | None = None
    prediction_drivers: dict[str, Any] | None = None
    top_home_players: list[MatchPlayerImpact] = Field(default_factory=list)
    top_away_players: list[MatchPlayerImpact] = Field(default_factory=list)
    best_captain_candidate: MatchPlayerImpact | None = None
    best_attacking_option: MatchPlayerImpact | None = None
    best_defensive_option: MatchPlayerImpact | None = None


class MatchPredictionResponse(BaseModel):
    """Full next-Gameweek match predictions response."""

    season: str | None = None
    latest_completed_gameweek: int | None = None
    predicted_gameweek: int | None = None
    generated_at: str | None = None
    count: int = Field(description="Number of fixtures predicted.")
    predictions: list[MatchPrediction] = Field(description="Match predictions for the upcoming gameweek.")


class SquadPlayer(BaseModel):
    """Player selected in the Squad Builder with selection metadata."""

    element: int | None = None
    name: str
    position: str
    team: str
    price: float = Field(description="Price in millions of pounds (e.g. 10.0 for £10.0m)")
    value: float | None = None
    predicted_points: float = Field(description="Authoritative predicted points / rank score used for selection")
    predicted_expected_points: float | None = None
    predicted_fpl_rank_score: float | None = None
    points_per_million: float = Field(description="predicted_points / price")
    selection_type: str = Field(description="core, value, or budget_constraint")
    selection_reason: str = Field(description="Authoritative reason player was chosen")
    is_starter: bool = True
    is_captain: bool = False
    is_vice_captain: bool = False
    photo_url: str | None = None


class SquadBuildRequest(BaseModel):
    """Request payload for building an optimized squad."""

    budget: float = Field(default=100.0, ge=40.0, le=200.0, description="Total squad budget in £M")
    formation: str = Field(default="4-4-2", description="Starting XI formation e.g. 4-4-2, 3-5-2")
    core_picks_count: int = Field(default=4, ge=1, le=8, description="Target number of core premium picks")


class SquadBuildResponse(BaseModel):
    """Complete 15-player squad response with budget, formation, and selection metadata."""

    season: str | None = None
    gameweek: int | None = None
    budget: float
    total_cost: float
    remaining_budget: float
    total_predicted_points: float
    formation: str
    count: int = Field(default=15, description="Squad size, always 15 for a complete valid squad")
    captain: SquadPlayer
    vice_captain: SquadPlayer
    starting_xi: list[SquadPlayer] = Field(description="11 starting players")
    bench: list[SquadPlayer] = Field(description="4 bench players (1 GK, 3 outfield)")
    squad: list[SquadPlayer] = Field(description="All 15 squad players")
    core_picks: list[SquadPlayer] = Field(default_factory=list, description="Core high-point picks")
    value_picks: list[SquadPlayer] = Field(default_factory=list, description="Value-for-money completion picks")
