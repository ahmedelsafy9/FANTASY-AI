"""Intelligent Query Classifier and Investigation Planner.

Implements the "Investigate First" architecture:
- Classifies user queries into 12 distinct functional categories
- Formulates an InvestigationPlan with target entities, required agents, and necessary tools
- Distinguishes fast single-tool lookups from complex multi-agent reasoning tasks
- Identifies missing user context (such as squad composition or budget) to prompt focused clarifications
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.agentic.conversation_state import ConversationState
from src.config.logging_config import get_logger

logger = get_logger(__name__)


# 12 Query Categories
INTENT_SIMPLE_LOOKUP = "simple_lookup"
INTENT_PLAYER_ANALYSIS = "player_analysis"
INTENT_PLAYER_COMPARISON = "player_comparison"
INTENT_TRANSFER_DECISION = "transfer_decision"
INTENT_SQUAD_ANALYSIS = "squad_analysis"
INTENT_CAPTAINCY = "captaincy"
INTENT_FIXTURE_ANALYSIS = "fixture_analysis"
INTENT_DIFFERENTIAL_SEARCH = "differential_search"
INTENT_INJURY_AVAILABILITY = "injury_availability"
INTENT_CHIP_STRATEGY = "chip_strategy"
INTENT_MULTI_FACTOR_DECISION = "multi_factor_decision"
INTENT_RESEARCH_QUESTION = "research_question"


@dataclass
class InvestigationPlan:
    """Explicit investigation plan created prior to agent execution.

    Attributes:
        intent: Classified query category.
        entities: Extracted or resolved player names.
        teams: Extracted team names.
        required_agents: Names of agents to invoke.
        required_tools: List of tools authorized and prioritized for this task.
        use_rag: Whether knowledge retrieval is strictly needed.
        rag_category: Category filter for RAG (e.g. 'rules', 'chips', 'strategy').
        is_complex: Whether multi-step cross-agent synthesis is required.
        missing_context: Name of missing context that prevents full resolution (e.g. 'user_squad').
        clarification_prompt: Focused question to ask user if missing context prevents decision.
        rationale: Internal rationale for the investigation plan.
    """

    intent: str
    entities: list[str] = field(default_factory=list)
    teams: list[str] = field(default_factory=list)
    required_agents: list[str] = field(default_factory=list)
    required_tools: list[str] = field(default_factory=list)
    use_rag: bool = False
    rag_category: str | None = None
    is_complex: bool = False
    missing_context: str | None = None
    clarification_prompt: str | None = None
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "entities": self.entities,
            "teams": self.teams,
            "required_agents": self.required_agents,
            "required_tools": self.required_tools,
            "use_rag": self.use_rag,
            "rag_category": self.rag_category,
            "is_complex": self.is_complex,
            "missing_context": self.missing_context,
            "clarification_prompt": self.clarification_prompt,
            "rationale": self.rationale,
        }


def classify_query_intent(query: str, entities: list[str], conversation: ConversationState | None = None) -> str:
    """Classify user query into one of the 12 functional categories."""
    lower = query.lower()
    num_players = len(entities)

    # 1. Rules and mechanics (Research)
    rules_keywords = [
        "how does", "how do", "how is", "what is the rule", "rule for", "scoring system",
        "bonus points", "bps work", "auto-sub", "clean sheet rule", "deadline rule",
        "how many transfers", "budget limit", "max players from", "red card ban",
    ]
    if any(kw in lower for kw in rules_keywords) and not any(kw in lower for kw in ["sell", "buy", "transfer", "captain"]):
        return INTENT_RESEARCH_QUESTION

    # 2. Chip Strategy & Blank/Double Gameweek Planning
    chip_keywords = [
        "wildcard", "free hit", "bench boost", "triple captain", "tc", "bb", "fh", "wc",
        "when should i use my wildcard", "when to play wildcard", "when to wildcard",
        "activate wildcard", "chip timing", "best time to use",
        "blank gameweek", "blank gw", "bgw", "double gameweek", "double gw", "dgw",
        "chip strategy", "blank and double",
    ]
    if any(kw in lower for kw in chip_keywords):
        return INTENT_CHIP_STRATEGY

    # 3. Squad Analysis & Risks
    squad_keywords = [
        "my squad", "my team", "analyze my team", "analyze my squad", "rate my team", "rmt",
        "biggest weakness", "weakest link", "weakness in my team", "biggest risk in my",
        "biggest risks in my", "team risks", "squad risks", "starting xi", "bench problem",
    ]
    if any(kw in lower for kw in squad_keywords):
        return INTENT_SQUAD_ANALYSIS

    # 4. Captaincy
    captain_keywords = [
        "captain", "captaincy", "who to captain", "who should i captain", "armband",
        "vice captain", "vc", "مين أكابتن", "كابتن", "كابتنة",
    ]
    if any(kw in lower for kw in captain_keywords):
        return INTENT_CAPTAINCY

    # 5. Transfer Decision / Hit evaluation
    transfer_keywords = [
        "sell", "buy", "replace", "transfer out", "transfer in", "swap", "bring in",
        "drop", "get rid of", "worth a hit", "-4 hit", "minus 4", "take a hit",
        "sell palmer for", "replace with",
    ]
    if any(kw in lower for kw in transfer_keywords) or (conversation and conversation.is_follow_up and conversation.follow_up_topic in ("alternative", "hit_strategy", "hold_sell")):
        return INTENT_TRANSFER_DECISION

    # 6. Differentials
    diff_keywords = [
        "differential", "differentials", "low ownership", "underowned", "punt", "hidden gem",
        "ownership below", "ownership under", "below 15%", "under 15%", "below 10%", "under 10%", "low-ownership",
    ]
    if any(kw in lower for kw in diff_keywords):
        return INTENT_DIFFERENTIAL_SEARCH

    # 7. Injury & Availability
    injury_keywords = [
        "injured", "injury", "injuries", "doubtful", "suspended", "suspension",
        "fit", "fitness", "fit to play", "is he fit", "available to play", "chance of playing",
        "team news", "press conference", "who is out", "who is doubtful", "ruled out", "مصاب", "إصابات",
    ]
    if any(kw in lower for kw in injury_keywords):
        return INTENT_INJURY_AVAILABILITY

    # 8. Fixtures
    fixture_keywords = [
        "fixtures", "fixture", "upcoming games", "next 5 gameweeks", "schedule",
        "fixture swing", "fdr", "easy games", "tough games",
    ]
    if any(kw in lower for kw in fixture_keywords) and num_players <= 1:
        return INTENT_FIXTURE_ANALYSIS

    # 9. Player Comparison
    comparison_phrases = [
        "compare", " vs ", " versus ", "better option", "who is better", "which one",
        "salah or saka", "palmer and saka",
    ]
    has_comp_word = any(p in lower for p in comparison_phrases) or bool(re.search(r"\b(vs|versus)\b", lower))
    has_or_between = bool(re.search(r"\b[A-Z][a-z]+\s+or\s+[A-Z][a-z]+", query))
    if num_players >= 2 or has_comp_word or has_or_between:
        return INTENT_PLAYER_COMPARISON

    # 10. Simple lookup vs Player analysis
    simple_lookup_keywords = [
        "who is", "what club", "what team does", "how much is", "price of", "position of",
    ]
    if any(kw in lower for kw in simple_lookup_keywords) and num_players == 1:
        return INTENT_SIMPLE_LOOKUP

    if num_players == 1:
        return INTENT_PLAYER_ANALYSIS

    # Default fallback
    if any(kw in lower for kw in ["should i", "recommend", "advice", "what to do"]):
        return INTENT_MULTI_FACTOR_DECISION

    return INTENT_PLAYER_ANALYSIS if num_players > 0 else INTENT_RESEARCH_QUESTION


def create_investigation_plan(
    query: str,
    entities: list[str],
    teams: list[str],
    user_context: dict[str, Any] | None = None,
    conversation: ConversationState | None = None,
) -> InvestigationPlan:
    """Create a structured InvestigationPlan for the user query."""
    intent = classify_query_intent(query, entities, conversation)
    ctx = user_context or {}
    squad_candidates = ctx.get("squad_names") or ctx.get("squad") or (conversation.user_squad if conversation else None) or (entities if len(entities) >= 3 else None)
    squad_provided = bool(squad_candidates)
    squad_count = len(squad_candidates) if squad_candidates else 0

    if intent == INTENT_SIMPLE_LOOKUP:
        return InvestigationPlan(
            intent=intent,
            entities=entities,
            teams=teams,
            required_agents=["player_analysis"],
            required_tools=["get_player_info"],
            use_rag=False,
            is_complex=False,
            rationale="Factual lookup for single entity. Single fast tool call.",
        )

    if intent == INTENT_PLAYER_ANALYSIS:
        return InvestigationPlan(
            intent=intent,
            entities=entities,
            teams=teams,
            required_agents=["player_analysis", "news_availability"],
            required_tools=["get_player_info", "get_player_form", "get_player_availability"],
            use_rag=False,
            is_complex=False,
            rationale="Individual player performance, form, minutes and fitness check.",
        )

    if intent == INTENT_PLAYER_COMPARISON:
        return InvestigationPlan(
            intent=intent,
            entities=entities,
            teams=teams,
            required_agents=["player_analysis", "fixture_transfer", "news_availability"],
            required_tools=["compare_players", "get_player_availability", "get_fixture_info", "get_player_form"],
            use_rag=False,
            is_complex=True,
            rationale="Head-to-head evaluation covering underlying stats, availability, and upcoming fixtures.",
        )

    if intent == INTENT_TRANSFER_DECISION:
        return InvestigationPlan(
            intent=intent,
            entities=entities,
            teams=teams,
            required_agents=["player_analysis", "fixture_transfer", "news_availability", "strategy"],
            required_tools=["analyze_transfer", "compare_players", "get_player_availability", "get_fixture_info", "get_player_form"],
            use_rag=False,
            is_complex=True,
            rationale="Full transfer investigation: evaluate player out vs player in across fitness, fixtures, form, and hit trade-offs.",
        )

    if intent == INTENT_SQUAD_ANALYSIS:
        missing = None
        clarification = None
        if not squad_provided:
            missing = "user_squad"
            clarification = (
                "I can analyze general Premier League trends, but I can't see your specific 15-man squad. "
                "Please share your starting XI or squad players, and I will pinpoint your biggest weakness, "
                "rotation risks, and top transfer priorities."
            )
        elif squad_count < 15:
            missing = "partial_squad"
            clarification = (
                f"Provisional analysis on {squad_count} provided players. Share your remaining "
                f"{15 - squad_count} players to evaluate bench depth and full starting XI formation."
            )

        return InvestigationPlan(
            intent=intent,
            entities=entities,
            teams=teams,
            required_agents=["squad_analysis", "news_availability", "fixture_transfer"],
            required_tools=["analyze_squad", "get_injured_doubtful_players", "get_captain_recommendation"] if squad_provided else ["get_injured_doubtful_players", "get_captain_recommendation"],
            use_rag=False,
            is_complex=True,
            missing_context=missing,
            clarification_prompt=clarification,
            rationale="Squad-level composition audit: evaluate provided players for weaknesses, rotation risks, and transfer priorities.",
        )

    if intent == INTENT_CAPTAINCY:
        return InvestigationPlan(
            intent=intent,
            entities=entities,
            teams=teams,
            required_agents=["squad_analysis", "player_analysis", "fixture_transfer", "news_availability"],
            required_tools=["get_captain_recommendation", "get_gameweek_predictions", "get_player_availability", "get_fixture_info"],
            use_rag=False,
            is_complex=True,
            rationale="Captaincy investigation: compare top projected assets against fixture difficulty, opponent defensive form, and minutes risk.",
        )

    if intent == INTENT_FIXTURE_ANALYSIS:
        return InvestigationPlan(
            intent=intent,
            entities=entities,
            teams=teams,
            required_agents=["fixture_transfer"],
            required_tools=["get_fixture_info", "get_current_gameweek"],
            use_rag=False,
            is_complex=False,
            rationale="Fixture difficulty ratings and fixture swing evaluation.",
        )

    if intent == INTENT_DIFFERENTIAL_SEARCH:
        return InvestigationPlan(
            intent=intent,
            entities=entities,
            teams=teams,
            required_agents=["strategy", "news_availability"],
            required_tools=["get_differential_picks", "get_player_availability"],
            use_rag=False,
            is_complex=False,
            rationale="Low-ownership gems with favorable underlying metrics and clean availability.",
        )

    if intent == INTENT_INJURY_AVAILABILITY:
        tools = ["get_player_availability"] if entities else ["get_injured_doubtful_players"]
        return InvestigationPlan(
            intent=intent,
            entities=entities,
            teams=teams,
            required_agents=["news_availability"],
            required_tools=tools,
            use_rag=False,
            is_complex=False,
            rationale="Medical, suspension and availability check grounded in latest Premier League press data.",
        )

    if intent == INTENT_CHIP_STRATEGY:
        return InvestigationPlan(
            intent=intent,
            entities=entities,
            teams=teams,
            required_agents=["strategy", "research"],
            required_tools=["get_current_gameweek", "get_gameweek_predictions"],
            use_rag=True,
            rag_category="chips",
            is_complex=True,
            rationale="Chip timing investigation: combine official FPL chip rules with upcoming fixture congestion and gameweek schedule.",
        )

    if intent == INTENT_RESEARCH_QUESTION:
        return InvestigationPlan(
            intent=intent,
            entities=entities,
            teams=teams,
            required_agents=["research"],
            required_tools=[],
            use_rag=True,
            rag_category="rules",
            is_complex=False,
            rationale="FPL rulebook and mechanics inquiry. Grounded in curated knowledge base.",
        )

    # Multi-factor decision
    return InvestigationPlan(
        intent=INTENT_MULTI_FACTOR_DECISION,
        entities=entities,
        teams=teams,
        required_agents=["player_analysis", "fixture_transfer", "strategy"],
        required_tools=["compare_players", "get_gameweek_predictions", "get_fixture_info"],
        use_rag=False,
        is_complex=True,
        rationale="Cross-cutting tactical decision requiring multi-agent consensus.",
    )
