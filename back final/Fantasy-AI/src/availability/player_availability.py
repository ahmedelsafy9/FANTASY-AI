"""Derives structured availability from raw FPL bootstrap-static fields.

The FPL API exposes five key availability signals per player:

- ``status``  → a / d / i / s / u
- ``chance_of_playing_next_round`` → None / 0 / 25 / 50 / 75 / 100
- ``chance_of_playing_this_round`` → same scale
- ``news``    → free-text injury/transfer/status explanation
- ``news_added`` → ISO-8601 timestamp of last news update

This module maps those raw signals to a richer, structured
:class:`PlayerAvailability` that both the prediction-adjustment
layer and the chatbot tools can consume.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from src.metadata.player_metadata import PlayerMetadata


@dataclass(frozen=True)
class PlayerAvailability:
    """Structured availability for a single player.

    Derived deterministically from official FPL API fields.
    Never fabricated — every flag traces back to a specific FPL field.
    """

    player_id: int
    availability_status: str
    """One of: fit, rotation_risk, doubtful, minor_injury, major_injury,
    suspended, ruled_out, unavailable."""

    injury_flag: bool
    doubt_flag: bool
    suspension_flag: bool
    ruled_out_flag: bool
    expected_to_start: bool | None
    expected_minutes: float
    rotation_risk: float
    team_news: str | None
    team_news_flag: bool
    source: str
    timestamp: str | None
    gameweek: int | None
    confidence: float | None
    chance_of_playing_next: int | None


# ---------------------------------------------------------------
# FPL status codes
# ---------------------------------------------------------------
# a = available  (green / no flag)
# d = doubtful   (yellow / orange flag)
# i = injured    (red flag)
# s = suspended  (red flag)
# u = unavailable / not in squad / left club
# n = not in squad (some seasons)
# ---------------------------------------------------------------

_SUSPENSION_PATTERNS = re.compile(
    r"suspend|red card|ban|serving", re.IGNORECASE
)
_TRANSFER_PATTERNS = re.compile(
    r"joined|loan|departed|left|transfer|sold|released|free agent",
    re.IGNORECASE,
)


def _classify_news(news: str | None) -> str | None:
    """Classify news text into a category hint."""
    if not news:
        return None
    if _SUSPENSION_PATTERNS.search(news):
        return "suspension"
    if _TRANSFER_PATTERNS.search(news):
        return "transfer"
    # Generic injury keywords
    lower = news.lower()
    for keyword in (
        "injury", "injured", "knee", "hamstring", "ankle", "groin",
        "calf", "thigh", "back", "hip", "shoulder", "foot", "muscle",
        "ligament", "fracture", "surgery", "operation", "concussion",
        "illness", "ill", "sick",
    ):
        if keyword in lower:
            return "injury"
    if "unknown return" in lower:
        return "long_term"
    return None


def derive_player_availability(
    meta: PlayerMetadata,
    *,
    historical_avg_minutes: float | None = None,
    gameweek: int | None = None,
    fetch_timestamp: str | None = None,
) -> PlayerAvailability:
    """Derive structured availability from a player's FPL metadata.

    Args:
        meta: The extended :class:`PlayerMetadata` (with availability
            fields populated from bootstrap-static).
        historical_avg_minutes: The player's recent average minutes
            (e.g. from ``minutes_avg_last_3`` or ``minutes_avg_last_5``
            in the engineered features).  Falls back to a season-level
            estimate if not provided.
        gameweek: The Gameweek being predicted for.
        fetch_timestamp: ISO-8601 timestamp of when the data was fetched.
            Falls back to ``meta.news_added`` if not provided.

    Returns:
        A fully populated :class:`PlayerAvailability`.
    """

    status = (meta.status or "a").lower()
    chance_next = meta.chance_of_playing_next_round
    news = meta.news
    news_category = _classify_news(news)

    # --- Baseline minutes estimate ---
    if historical_avg_minutes is not None and historical_avg_minutes > 0:
        baseline_minutes = historical_avg_minutes
    elif meta.minutes_season is not None and meta.starts_season is not None:
        if meta.starts_season > 0:
            baseline_minutes = meta.minutes_season / meta.starts_season
        else:
            baseline_minutes = 0.0
    else:
        baseline_minutes = 0.0

    # --- Derive availability_status ---
    availability_status: str
    injury_flag = False
    doubt_flag = False
    suspension_flag = False
    ruled_out_flag = False
    expected_to_start: bool | None = None
    expected_minutes: float
    rotation_risk_score: float = 0.0
    confidence: float | None = None

    if status == "u":
        # Unavailable — left club, loaned out, etc.
        availability_status = "unavailable"
        ruled_out_flag = True
        expected_minutes = 0.0
        expected_to_start = False
        confidence = 1.0

    elif status == "s":
        # Suspended
        availability_status = "suspended"
        suspension_flag = True
        ruled_out_flag = True
        expected_minutes = 0.0
        expected_to_start = False
        confidence = 1.0

    elif status == "i":
        # Injured
        injury_flag = True
        if chance_next is not None and chance_next > 0:
            availability_status = "minor_injury"
            factor = chance_next / 100.0
            expected_minutes = factor * baseline_minutes
            expected_to_start = chance_next >= 75
            doubt_flag = True
            confidence = 0.6
        else:
            availability_status = "major_injury"
            ruled_out_flag = True
            expected_minutes = 0.0
            expected_to_start = False
            confidence = 0.9

    elif status == "d":
        # Doubtful
        doubt_flag = True
        if news_category == "suspension":
            availability_status = "suspended"
            suspension_flag = True
            expected_minutes = 0.0
            expected_to_start = False
            confidence = 0.8
        elif chance_next is not None:
            if chance_next == 0:
                availability_status = "ruled_out"
                ruled_out_flag = True
                expected_minutes = 0.0
                expected_to_start = False
                confidence = 0.85
            elif chance_next <= 25:
                availability_status = "minor_injury"
                injury_flag = True
                expected_minutes = 0.25 * baseline_minutes
                expected_to_start = False
                confidence = 0.6
            elif chance_next <= 50:
                availability_status = "doubtful"
                expected_minutes = 0.50 * baseline_minutes
                expected_to_start = False
                confidence = 0.5
            else:
                # 75%
                availability_status = "doubtful"
                expected_minutes = 0.75 * baseline_minutes
                expected_to_start = True  # likely but uncertain
                confidence = 0.55
        else:
            # Doubtful with no chance info
            availability_status = "doubtful"
            expected_minutes = 0.50 * baseline_minutes
            expected_to_start = None
            confidence = 0.4

    elif status == "a":
        # Available
        if chance_next is not None and chance_next < 100:
            if chance_next <= 50:
                availability_status = "doubtful"
                doubt_flag = True
                expected_minutes = (chance_next / 100.0) * baseline_minutes
                expected_to_start = False
                confidence = 0.5
            else:
                # 75% — rotation risk
                availability_status = "rotation_risk"
                rotation_risk_score = 0.4
                expected_minutes = 0.75 * baseline_minutes
                expected_to_start = True
                confidence = 0.6
        else:
            # Fully fit / expected starter
            availability_status = "fit"
            expected_minutes = baseline_minutes
            expected_to_start = baseline_minutes >= 45
            confidence = 0.8
    else:
        # Unknown status code — treat as fit
        availability_status = "fit"
        expected_minutes = baseline_minutes
        expected_to_start = None
        confidence = 0.3

    # Ensure expected_minutes stays in [0, 90]
    expected_minutes = max(0.0, min(90.0, expected_minutes))

    # Determine timestamp
    timestamp = meta.news_added or fetch_timestamp

    return PlayerAvailability(
        player_id=meta.player_id,
        availability_status=availability_status,
        injury_flag=injury_flag,
        doubt_flag=doubt_flag,
        suspension_flag=suspension_flag,
        ruled_out_flag=ruled_out_flag,
        expected_to_start=expected_to_start,
        expected_minutes=round(expected_minutes, 1),
        rotation_risk=round(rotation_risk_score, 3),
        team_news=news,
        team_news_flag=bool(news),
        source="fpl_official",
        timestamp=timestamp,
        gameweek=gameweek,
        confidence=confidence,
        chance_of_playing_next=chance_next,
    )


def derive_all_availability(
    player_metadata: dict[int, PlayerMetadata],
    *,
    minutes_lookup: dict[int, float] | None = None,
    gameweek: int | None = None,
    fetch_timestamp: str | None = None,
) -> dict[int, PlayerAvailability]:
    """Derive availability for every player in the metadata lookup.

    Args:
        player_metadata: Full player-ID → PlayerMetadata mapping.
        minutes_lookup: Optional player-ID → average-minutes mapping
            from engineered features.
        gameweek: The Gameweek being predicted for.
        fetch_timestamp: When the source data was fetched.

    Returns:
        A player-ID → PlayerAvailability mapping.
    """
    result: dict[int, PlayerAvailability] = {}
    for pid, meta in player_metadata.items():
        avg_mins = (minutes_lookup or {}).get(pid)
        result[pid] = derive_player_availability(
            meta,
            historical_avg_minutes=avg_mins,
            gameweek=gameweek,
            fetch_timestamp=fetch_timestamp,
        )
    return result
