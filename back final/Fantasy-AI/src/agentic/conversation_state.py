"""Conversation State and Memory Tracking for Agentic AI.

Maintains multi-turn context across user interactions:
- Active players and teams under discussion
- Prior intents and recommendations
- Squad context provided by the user
- Resolves pronoun and follow-up references (e.g. "What about Saka instead?", "Who has better fixtures?")
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ConversationState:
    """Lightweight conversation state tracked across conversation turns."""

    active_players: list[str] = field(default_factory=list)
    active_teams: list[str] = field(default_factory=list)
    last_intent: str | None = None
    last_recommendation: str | None = None
    user_squad: list[str] = field(default_factory=list)
    gameweek: int | None = None
    is_follow_up: bool = False
    follow_up_topic: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_players": self.active_players,
            "active_teams": self.active_teams,
            "last_intent": self.last_intent,
            "last_recommendation": self.last_recommendation,
            "user_squad": self.user_squad,
            "gameweek": self.gameweek,
            "is_follow_up": self.is_follow_up,
            "follow_up_topic": self.follow_up_topic,
        }


# Follow-up trigger patterns
_FOLLOW_UP_PATTERNS = [
    (re.compile(r"\b(?:what\s+about|how\s+about|instead\s+of|instead)\b", re.I), "alternative"),
    (re.compile(r"\b(?:who\s+has\s+better\s+fixtures|which\s+(?:one\s+)?has\s+better\s+fixtures|which\s+fixtures|easier\s+fixtures|better\s+fixtures)\b", re.I), "fixtures"),
    (re.compile(r"\b(?:what\s+if\s+i\s+take\s+a\s+-4|take\s+a\s+hit|minus\s+4|-4\s+hit|worth\s+a\s+hit|for\s+a\s+-4|make\s+the\s+transfer\s+for\s+a\s+-4|would\s+you\s+make\s+the\s+transfer)\b", re.I), "hit_strategy"),
    (re.compile(r"\b(?:then\s+who|who\s+then|then\s+who\s+should\s+i\s+captain)\b", re.I), "captaincy"),
    (re.compile(r"\b(?:why|why\s+him|why\s+them|explain\s+why)\b", re.I), "explanation"),
    (re.compile(r"\b(?:keep\s+or\s+sell|hold\s+or\s+sell)\b", re.I), "hold_sell"),
    (re.compile(r"\b(?:which\s+one|who\s+is\s+better|which\s+should\s+i\s+pick|which\s+one\s+to\s+pick)\b", re.I), "comparison"),
]


def extract_conversation_state(
    history: list[dict[str, str]] | None,
    current_query: str,
    known_player_names: list[str] | None = None,
) -> ConversationState:
    """Extract and resolve multi-turn conversation context.

    Args:
        history: Prior conversation turns [{'role': 'user'/'assistant', 'content': '...'}].
        current_query: Current turn message.
        known_player_names: Pre-extracted player names from current query.

    Returns:
        ConversationState with active entities and follow-up flags.
    """
    state = ConversationState()
    current_players = list(known_player_names or [])

    if not history:
        state.active_players = current_players
        if len(current_players) >= 3 or re.search(r"\b(?:my\s+(?:team|squad)|these\s+\d+\s+players)\b", current_query, re.I):
            state.user_squad = current_players
        return state

    # 1. Parse prior turns for mentioned players & recommendations
    prior_players: list[str] = []
    prior_teams: list[str] = []
    last_intent = None
    last_recommendation = None
    existing_user_squad: list[str] = []

    # Scan last 4 messages in history
    recent_history = history[-4:]
    for msg in recent_history:
        content = msg.get("content", "")
        role = msg.get("role", "")

        # Ignore markdown header lines to avoid false entities like "Transfer Decision"
        clean_lines = [l for l in content.split("\n") if not l.strip().startswith("#")]
        content_to_scan = "\n".join(clean_lines)

        # Extract capitalised tokens likely to be player names
        words = re.findall(r"\b[A-Z][a-z]{2,}(?:\s[A-Z][a-z]+)?\b", content_to_scan)
        for w in words:
            # Clean verb prefixes (e.g. "Compare Watkins" -> "Watkins")
            cleaned_w = re.sub(
                r"^(?:Compare|Analyze|Evaluate|Between|Recommend|Versus|Transfer|Decision|Squad|Team|Notice|Provisional)\s+",
                "",
                w.strip(),
                flags=re.I,
            ).strip()

            if not cleaned_w:
                continue

            # Basic stop words filter
            if cleaned_w not in {
                "Should", "Would", "Could", "Which", "Where", "What", "When", "Who", "How",
                "Give", "Tell", "Find", "Best", "Good", "Bad", "Keep", "Drop", "Buy", "Sell",
                "Captain", "Vice", "Wildcard", "Free", "Hit", "Gameweek", "Premier", "League",
                "Assistant", "Fantasy", "Yes", "Not", "Decision", "Recommendation", "Verdict",
                "Why", "The", "Here", "Based", "Both", "First", "Second", "Option", "Winner",
                "Medical", "Availability", "Report", "Expected", "Points", "Head", "Transfer",
                "Analyst", "Assessment", "Player", "Players", "Notice", "Provisional", "Analysis",
                "Catch", "Risk", "Risks", "Considerations", "Armband", "Dossier", "Strategic",
                "Rulebook", "Mechanics", "Hold", "Sell", "Trade", "Cost",
            }:
                if cleaned_w not in prior_players:
                    prior_players.append(cleaned_w)

        if role == "assistant" and ("My pick:" in content or "Verdict:" in content or "Recommendation:" in content):
            last_recommendation = content[:200]

    state.active_teams = prior_teams
    state.last_intent = last_intent
    state.last_recommendation = last_recommendation

    # 2. Check if current query is a follow-up or has anaphora
    current_lower = current_query.lower()
    for pattern, topic in _FOLLOW_UP_PATTERNS:
        if pattern.search(current_lower):
            state.is_follow_up = True
            state.follow_up_topic = topic
            break

    has_anaphora = bool(re.search(
        r"\b(?:which\s+one|who\s+has|better\s+fixtures|either|both|him|he|them|the\s+transfer|for\s+a\s+-4)\b",
        current_lower,
    ))

    # 3. Squad tracking
    if len(current_players) >= 3 or re.search(r"\b(?:my\s+(?:team|squad)|these\s+\d+\s+players)\b", current_query, re.I):
        state.user_squad = current_players

    # 4. Resolve active players safely without polluting new topics
    if state.is_follow_up or has_anaphora:
        if current_players:
            # If user introduces a new alternative (e.g. "What about Havertz instead?"):
            # Put the new candidate first, and retain the previous target
            combined = list(current_players)
            for p in prior_players:
                if p not in combined and len(combined) < 2:
                    combined.append(p)
            state.active_players = combined
        else:
            # Reference without explicit entity names (e.g. "Which one has better fixtures?", "Would you make the transfer for a -4?"):
            state.active_players = prior_players[:2]
    else:
        # Fresh standalone query: strictly use current_players!
        # Prevents old conversation context from overriding explicit entities in a new request
        state.active_players = current_players

    logger.debug(
        "Extracted conversation state: is_follow_up=%s, active_players=%s, topic=%s",
        state.is_follow_up,
        state.active_players,
        state.follow_up_topic,
    )
    return state
