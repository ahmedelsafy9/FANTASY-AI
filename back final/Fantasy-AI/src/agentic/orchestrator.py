"""Agent Orchestrator: routes user requests to appropriate agents.

The orchestrator implements the "Investigate First" architecture:
1. Understands intent via intelligent 12-category query classification
2. Resolves multi-turn conversation state & entity memory
3. Formulates an explicit InvestigationPlan (agents, tools, RAG, factor matrix)
4. Coordinates and executes specialized domain agents
5. Selectively retrieves RAG knowledge only when required (rules, chips)
6. Synthesizes multi-agent evidence via the DecisionEngine into clear verdicts
7. Prepares structured context and formatting guidelines for the LLM
"""

from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from src.agentic.agents.base import AgentResult, BaseAgent
from src.agentic.agents.fixture_agent import FixtureTransferAgent
from src.agentic.agents.news_agent import NewsAvailabilityAgent
from src.agentic.agents.player_agent import PlayerAnalysisAgent
from src.agentic.agents.research_agent import ResearchAgent
from src.agentic.agents.squad_agent import SquadAnalysisAgent
from src.agentic.agents.strategy_agent import StrategyAgent
from src.agentic.conversation_state import ConversationState, extract_conversation_state
from src.agentic.decision_engine import DecisionEngine, SynthesizedDecision
from src.agentic.planner import (
    INTENT_RESEARCH_QUESTION,
    INTENT_SIMPLE_LOOKUP,
    InvestigationPlan,
    create_investigation_plan,
)
from src.agentic.rag.retriever import KnowledgeRetriever
from src.agentic.tools.definitions import build_tool_registry
from src.agentic.tools.registry import ToolRegistry
from src.api.state import AppState
from src.config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class OrchestratorResult:
    """Complete result from the orchestrator.

    Contains all agent results, tool calls made, knowledge context,
    the explicit investigation plan, the synthesized decision, and
    a structured data payload for the LLM.

    Attributes:
        agent_results: Results from each invoked agent.
        all_tool_calls: Flattened list of all tool calls across agents.
        knowledge_context: Combined knowledge from RAG.
        context_for_llm: Structured data to inject into the LLM prompt.
        agents_used: Names of agents that were invoked.
        total_time_ms: Total orchestration time.
        plan: The investigation plan that was executed.
        decision: The cross-agent decision synthesized from evidence.
        formatted_fallback: Pre-rendered expert decision response (used when LLM is offline).
    """

    agent_results: list[AgentResult] = field(default_factory=list)
    all_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    knowledge_context: dict[str, Any] | None = None
    context_for_llm: str = ""
    agents_used: list[str] = field(default_factory=list)
    total_time_ms: float = 0.0
    plan: InvestigationPlan | None = None
    decision: SynthesizedDecision | None = None
    formatted_fallback: str = ""


def _clean_extracted_name(name: str) -> str:
    """Clean query verbs and punctuation from extracted player name candidates."""
    cleaned = re.sub(
        r"^(?:compare|analyze|evaluate|between|recommend|versus|vs|and|or|for|with|about|tell\s+me\s+about|is|who|replace|sell|buy)\s+",
        "",
        name.strip(),
        flags=re.IGNORECASE,
    ).strip()
    return cleaned


def _extract_player_names(query: str) -> list[str]:
    """Extract potential player names from a query using pattern heuristics."""
    raw_names: list[str] = []

    # Pattern: X vs Y / X or Y / X and Y / X with Y
    vs_pattern = re.search(
        r"(\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\s+(?:vs|versus|or|and|with)\s+"
        r"(\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)?)",
        query,
    )
    if vs_pattern:
        raw_names.extend([vs_pattern.group(1), vs_pattern.group(2)])

    # Pattern: "replace X with Y" / "sell X buy Y" / "sell X for Y" / "X for Y"
    transfer_pattern = re.search(
        r"(?:replace|sell|drop|remove|transfer out)\s+(\b[A-Z][a-z]+)"
        r".*?(?:with|for|buy|bring in|get|transfer in)\s+(\b[A-Z][a-z]+)",
        query, re.IGNORECASE,
    )
    if transfer_pattern and not raw_names:
        raw_names.extend([transfer_pattern.group(1), transfer_pattern.group(2)])

    # Arabic patterns for comparison or transfer
    if not raw_names:
        ar_vs = re.search(r"(\b[A-Z][a-z]+)\s+(?:ولا|او|أو|ضد)\s+(\b[A-Z][a-z]+)", query)
        if ar_vs:
            raw_names.extend([ar_vs.group(1), ar_vs.group(2)])

    # Single capitalized player name (for "tell me about Palmer")
    if not raw_names:
        singles = re.findall(r"\b([A-Z][a-z]{2,}(?:\s[A-Z][a-z]+)?)\b", query)
        raw_names.extend(singles)

    stop_words = {
        "Should", "Would", "Could", "Which", "Where", "What",
        "When", "Who", "How", "Give", "Tell", "Find", "Best",
        "Good", "Bad", "Keep", "Drop", "Buy", "Sell", "The",
        "This", "That", "From", "With", "Analyze", "Compare",
        "Captain", "Wildcard", "Bench", "Triple", "Free", "Hit",
        "Build", "Risk", "Safe", "High", "Low", "Yes", "Not",
        "Are", "Is", "Am", "Was", "Were", "Has", "Have", "Had",
        "Do", "Does", "Did", "Can", "There", "Any", "All", "Some",
        "Please", "Players", "Player", "Injured", "Injury", "Doubts",
        "Team", "Squad", "Starting", "Bank", "Move", "Sense", "Makes", "Most",
        "Premier", "League", "Fantasy", "Week", "Gameweek",
        "Arsenal", "Liverpool", "Chelsea", "Man", "City",
        "United", "Tottenham", "Newcastle", "Brighton",
        "Aston", "Villa", "West", "Ham", "Crystal", "Palace",
        "Everton", "Fulham", "Wolves", "Bournemouth",
        "Brentford", "Nottingham", "Forest", "Burnley",
        "Sheffield", "Luton", "Ipswich", "Leicester",
        "Southampton",
    }

    cleaned_names: list[str] = []
    for candidate in raw_names:
        cleaned = _clean_extracted_name(candidate)
        if cleaned and cleaned not in stop_words and cleaned not in cleaned_names:
            cleaned_names.append(cleaned)

    return cleaned_names[:15]


def _extract_team_name(query: str) -> str | None:
    """Extract a Premier League team name from a query."""
    teams = [
        "Arsenal", "Aston Villa", "Bournemouth", "Brentford",
        "Brighton", "Burnley", "Chelsea", "Crystal Palace",
        "Everton", "Fulham", "Ipswich", "Leicester",
        "Liverpool", "Luton", "Man City", "Man Utd",
        "Manchester City", "Manchester United",
        "Newcastle", "Nott'm Forest", "Nottingham Forest",
        "Sheffield Utd", "Southampton", "Spurs", "Tottenham",
        "West Ham", "Wolves", "Wolverhampton",
    ]
    lower = query.lower()
    for team in teams:
        if team.lower() in lower:
            return team
    return None


class AgentOrchestrator:
    """Investigative orchestrator implementing the Investigate-First architecture."""

    def __init__(self, app_state: AppState) -> None:
        self._state = app_state
        self._registry = build_tool_registry(app_state)
        self._retriever = KnowledgeRetriever()
        self._retriever.initialize()
        self._decision_engine = DecisionEngine()

        # Initialize all specialized domain agents
        self._agents: dict[str, BaseAgent] = {
            "player_analysis": PlayerAnalysisAgent(self._registry),
            "squad_analysis": SquadAnalysisAgent(self._registry),
            "fixture_transfer": FixtureTransferAgent(self._registry),
            "news_availability": NewsAvailabilityAgent(self._registry),
            "strategy": StrategyAgent(self._registry, self._retriever),
            "research": ResearchAgent(self._registry, self._retriever),
        }

        logger.info(
            "AgentOrchestrator initialized: %d agents, %d tools, %d knowledge chunks.",
            len(self._agents),
            self._registry.count,
            self._retriever._store.chunk_count if self._retriever.is_ready else 0,
        )

    @property
    def tool_registry(self) -> ToolRegistry:
        return self._registry

    @property
    def retriever(self) -> KnowledgeRetriever:
        return self._retriever

    def process(
        self,
        query: str,
        user_context: dict[str, Any] | None = None,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> OrchestratorResult:
        """Execute an investigative plan across agents and synthesize decision."""
        start = time.perf_counter()

        # 1. Named entity extraction
        extracted_names = _extract_player_names(query)
        team_name = _extract_team_name(query)
        teams = [team_name] if team_name else []

        # 2. Conversation state resolution (multi-turn memory)
        conv_state = extract_conversation_state(
            conversation_history,
            query,
            known_player_names=extracted_names,
        )
        resolved_entities = conv_state.active_players if conv_state.active_players else extracted_names

        # 3. Formulate Investigation Plan
        plan = create_investigation_plan(
            query=query,
            entities=resolved_entities,
            teams=teams,
            user_context=user_context,
            conversation=conv_state,
        )

        logger.info(
            "InvestigationPlan created: intent='%s', entities=%s, agents=%s, is_complex=%s",
            plan.intent,
            plan.entities,
            plan.required_agents,
            plan.is_complex,
        )

        # 4. Context for agents
        agent_context = dict(user_context or {})
        agent_context["player_names"] = plan.entities
        if teams:
            agent_context["team_name"] = teams[0]
        if conv_state.user_squad:
            agent_context["squad_names"] = conv_state.user_squad

        # 5. Agent selection and execution
        selected_agents: list[BaseAgent] = []
        for agent_name in plan.required_agents:
            if agent_name in self._agents:
                selected_agents.append(self._agents[agent_name])

        # Enforce budget: max 3 agents to prevent runaway execution
        selected_agents = selected_agents[:3]

        # Execute agents
        agent_results: list[AgentResult] = []
        all_tool_calls: list[dict[str, Any]] = []
        knowledge_context: dict[str, Any] | None = None

        # Execute agents safely
        for agent in selected_agents:
            try:
                res = agent.analyze(query, agent_context)
                agent_results.append(res)
                all_tool_calls.extend(res.tool_calls)

                if res.knowledge_context and res.knowledge_context.get("has_knowledge"):
                    knowledge_context = res.knowledge_context
            except Exception as exc:
                logger.exception("Agent '%s' failed during investigation: %s", agent.name, exc)

        # 6. RAG Retrieval if planned but not yet fetched
        if plan.use_rag and (not knowledge_context or not knowledge_context.get("has_knowledge")):
            try:
                cat = plan.rag_category
                knowledge_context = self._retriever.retrieve_as_context(
                    query, category=cat, top_k=3
                )
            except Exception as exc:
                logger.warning("RAG retrieval failed: %s", exc)

        # 7. Synthesize evidence into a decision
        decision = self._decision_engine.synthesize(plan, agent_results, knowledge_context)

        # 8. Build structured LLM context
        context_for_llm = self._build_llm_context(
            query=query,
            plan=plan,
            decision=decision,
            agent_results=agent_results,
            knowledge_context=knowledge_context,
        )

        elapsed = (time.perf_counter() - start) * 1000

        logger.info(
            "Orchestrator completed in %.1fms: %d agents, %d tool calls, intent='%s'",
            elapsed,
            len(agent_results),
            len(all_tool_calls),
            plan.intent,
        )

        return OrchestratorResult(
            agent_results=agent_results,
            all_tool_calls=all_tool_calls,
            knowledge_context=knowledge_context,
            context_for_llm=context_for_llm,
            agents_used=[a.agent_name for a in agent_results],
            total_time_ms=round(elapsed, 1),
            plan=plan,
            decision=decision,
            formatted_fallback=decision.formatted_text,
        )

    def _build_llm_context(
        self,
        query: str,
        plan: InvestigationPlan,
        decision: SynthesizedDecision,
        agent_results: list[AgentResult],
        knowledge_context: dict[str, Any] | None,
    ) -> str:
        """Format the investigation findings and decision matrix into structured LLM instructions."""
        parts: list[str] = []

        parts.append("=== INVESTIGATION PLAN & INTENT ===")
        parts.append(f"Intent Category: {plan.intent}")
        parts.append(f"Target Entities: {', '.join(plan.entities) if plan.entities else 'None'}")
        parts.append(f"Investigation Rationale: {plan.rationale}")
        parts.append("")

        parts.append("=== AGENT ANALYSIS RESULTS ===\n")
        for res in agent_results:
            parts.append(f"--- Agent: {res.agent_name} (Status: {res.status}) ---")
            if res.summary:
                parts.append(f"Summary: {res.summary}")

            # Include findings if available
            if res.findings:
                for f in res.findings:
                    parts.append(f"  • [{f.factor.upper()}] {f.player or ''}: {f.assessment} — {f.summary}")

            # Include raw data
            try:
                analysis_str = json.dumps(res.analysis, default=str, indent=None)
                if len(analysis_str) > 3000:
                    analysis_str = analysis_str[:3000] + "... [truncated]"
                parts.append(f"Data: {analysis_str}")
            except Exception:
                parts.append("Data: [unavailable]")
            parts.append("")

        if knowledge_context and knowledge_context.get("has_knowledge"):
            parts.append("=== RETRIEVED KNOWLEDGE BASE (FPL Rules / Mechanics) ===")
            parts.append("NOTE: This is curated static knowledge. Never use it to contradict live player data.")
            for chunk in knowledge_context.get("chunks", []):
                parts.append(f"[{chunk.get('title', 'Rules')}]: {chunk.get('text', '')[:400]}")
            parts.append("")

        parts.append("=== SYNTHESIZED DECISION MATRIX ===")
        parts.append(f"Recommended Decision: {decision.recommendation}")
        if decision.why:
            parts.append("Key Supporting Factors:")
            for w in decision.why:
                parts.append(f"  - {w}")
        if decision.risks_and_catches:
            parts.append("Risks & Nuances:")
            for r in decision.risks_and_catches:
                parts.append(f"  - {r}")
        if decision.verdict:
            parts.append(f"Verdict: {decision.verdict}")
        if decision.sources:
            parts.append(f"Data Sources: {', '.join(decision.sources)}")
        parts.append("")

        parts.append("=== RESPONSE FORMAT INSTRUCTIONS ===")
        parts.append("Act as a decisive Fantasy Premier League analyst. Follow this structure strictly:")
        if plan.intent in ("transfer_decision", "player_comparison"):
            parts.append("1. State the winner / pick clearly upfront ('My pick: [Player]' or 'Recommendation: [Move]').")
            parts.append("2. Provide 2-3 concise bullet points under 'Why' citing expected points, form, or fixtures.")
            parts.append("3. Highlight 'The catch / Risks' (injury doubt, rotation, or -4 hit penalty).")
            parts.append("4. Conclude with a crisp 'Verdict' (distinguish free transfer vs hit).")
        elif plan.intent == "squad_analysis" and plan.missing_context:
            parts.append("Politely ask for the user's specific starting XI/squad players so you can evaluate their team accurately.")
        elif plan.intent == "chip_strategy":
            parts.append("State clearly whether to hold or activate the chip, the gameweek window rationale, and trigger conditions.")
        else:
            parts.append("Provide a direct, factual, data-backed answer without generic fluff.")
        parts.append("=== END ANALYSIS ===")

        return "\n".join(parts)
