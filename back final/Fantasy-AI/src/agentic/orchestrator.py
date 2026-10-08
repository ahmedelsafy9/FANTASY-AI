"""Agent Orchestrator: routes user requests to appropriate agents.

The orchestrator decides:
- Which agent(s) are needed for a request
- Whether additional information is required
- How to combine results from multiple agents
- What knowledge context to inject

For simple questions, it uses the minimum required tools.
For complex questions, it coordinates multiple specialized agents.

The orchestrator does NOT generate the final natural-language response
itself — it gathers structured data and passes it to the LLM via
the existing ChatbotService integration.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

from src.agentic.agents.base import AgentResult, BaseAgent
from src.agentic.agents.fixture_agent import FixtureTransferAgent
from src.agentic.agents.news_agent import NewsAvailabilityAgent
from src.agentic.agents.player_agent import PlayerAnalysisAgent
from src.agentic.agents.research_agent import ResearchAgent
from src.agentic.agents.squad_agent import SquadAnalysisAgent
from src.agentic.agents.strategy_agent import StrategyAgent
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
    and a structured data payload for the LLM.

    Attributes:
        agent_results: Results from each invoked agent.
        all_tool_calls: Flattened list of all tool calls across agents.
        knowledge_context: Combined knowledge from RAG.
        context_for_llm: Structured data to inject into the LLM prompt.
        agents_used: Names of agents that were invoked.
        total_time_ms: Total orchestration time.
    """

    agent_results: list[AgentResult] = field(default_factory=list)
    all_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    knowledge_context: dict[str, Any] | None = None
    context_for_llm: str = ""
    agents_used: list[str] = field(default_factory=list)
    total_time_ms: float = 0.0


def _extract_player_names(query: str) -> list[str]:
    """Extract potential player names from a query.

    Uses heuristics (not an LLM) to pull out likely player references.
    The chatbot tools handle fuzzy resolution, so approximate extraction
    is sufficient.

    Args:
        query: User's query text.

    Returns:
        List of likely player name strings.
    """
    # Common patterns: "Palmer vs Saka", "replace Palmer with Saka",
    # "should I sell Palmer", "compare Haaland and Salah"
    names: list[str] = []

    # Pattern: X vs Y / X or Y / X and Y
    vs_pattern = re.search(
        r"(\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\s+(?:vs|versus|or|and|with)\s+"
        r"(\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)?)",
        query,
    )
    if vs_pattern:
        names.extend([vs_pattern.group(1), vs_pattern.group(2)])

    # Pattern: "replace X with Y" / "sell X buy Y" / "X → Y"
    transfer_pattern = re.search(
        r"(?:replace|sell|drop|remove|transfer out)\s+(\b[A-Z][a-z]+)"
        r".*?(?:with|for|buy|bring in|get|transfer in)\s+(\b[A-Z][a-z]+)",
        query, re.IGNORECASE,
    )
    if transfer_pattern and not names:
        names.extend([transfer_pattern.group(1), transfer_pattern.group(2)])

    # Pattern: single capitalized player name (for "tell me about Palmer")
    if not names:
        singles = re.findall(r"\b([A-Z][a-z]{2,}(?:\s[A-Z][a-z]+)?)\b", query)
        # Filter out common English words that are capitalized
        stop_words = {
            "Should", "Would", "Could", "Which", "Where", "What",
            "When", "Who", "How", "Give", "Tell", "Find", "Best",
            "Good", "Bad", "Keep", "Drop", "Buy", "Sell", "The",
            "This", "That", "From", "With", "Analyze", "Compare",
            "Captain", "Wildcard", "Bench", "Triple", "Free", "Hit",
            "Build", "Risk", "Safe", "High", "Low", "Yes", "Not",
            "Premier", "League", "Fantasy", "Week", "Gameweek",
            "Arsenal", "Liverpool", "Chelsea", "Man", "City",
            "United", "Tottenham", "Newcastle", "Brighton",
            "Aston", "Villa", "West", "Ham", "Crystal", "Palace",
            "Everton", "Fulham", "Wolves", "Bournemouth",
            "Brentford", "Nottingham", "Forest", "Burnley",
            "Sheffield", "Luton", "Ipswich", "Leicester",
            "Southampton",
        }
        for name in singles:
            if name not in stop_words:
                names.append(name)

    return names[:3]  # Cap at 3 names


def _extract_team_name(query: str) -> str | None:
    """Extract a team name from a query."""
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
    """Routes user requests to specialized agents and combines results.

    The orchestrator:
    1. Classifies the user's intent
    2. Extracts context (player names, team names, etc.)
    3. Selects relevant agents
    4. Invokes agents with appropriate context
    5. Combines results into a structured payload
    6. Returns data for the LLM to generate the final response

    Usage::

        orchestrator = AgentOrchestrator(app_state)
        result = orchestrator.process("Should I replace Palmer with Saka?")
        # result.context_for_llm contains structured data for the LLM
    """

    def __init__(self, app_state: AppState) -> None:
        self._state = app_state
        self._registry = build_tool_registry(app_state)
        self._retriever = KnowledgeRetriever()
        self._retriever.initialize()

        # Initialize all agents
        self._agents: list[BaseAgent] = [
            PlayerAnalysisAgent(self._registry),
            SquadAnalysisAgent(self._registry),
            FixtureTransferAgent(self._registry),
            NewsAvailabilityAgent(self._registry),
            StrategyAgent(self._registry, self._retriever),
            ResearchAgent(self._registry, self._retriever),
        ]

        logger.info(
            "AgentOrchestrator initialized: %d agents, %d tools, "
            "%d knowledge chunks.",
            len(self._agents),
            self._registry.count,
            self._retriever._store.chunk_count if self._retriever.is_ready else 0,
        )

    @property
    def tool_registry(self) -> ToolRegistry:
        """The orchestrator's tool registry."""
        return self._registry

    @property
    def retriever(self) -> KnowledgeRetriever:
        """The orchestrator's knowledge retriever."""
        return self._retriever

    def process(
        self,
        query: str,
        user_context: dict[str, Any] | None = None,
    ) -> OrchestratorResult:
        """Process a user request through the agent system.

        Args:
            query: The user's message.
            user_context: Optional context (e.g., squad, preferences).

        Returns:
            An :class:`OrchestratorResult` with structured data.
        """
        start = time.perf_counter()

        # 1. Extract context from the query
        context = self._build_context(query, user_context)

        # 2. Score and select agents
        selected = self._select_agents(query, max_agents=3)

        logger.info(
            "Orchestrator: query='%s', selected_agents=%s, "
            "player_names=%s",
            query[:80],
            [a.name for a in selected],
            context.get("player_names", []),
        )

        # 3. Invoke selected agents
        agent_results: list[AgentResult] = []
        all_tool_calls: list[dict[str, Any]] = []
        knowledge_context: dict[str, Any] | None = None

        for agent in selected:
            try:
                result = agent.analyze(query, context)
                agent_results.append(result)
                all_tool_calls.extend(result.tool_calls)

                if result.knowledge_context and result.knowledge_context.get("has_knowledge"):
                    knowledge_context = result.knowledge_context

            except Exception as exc:
                logger.exception(
                    "Agent '%s' failed: %s", agent.name, exc
                )

        # 4. Build LLM context
        context_for_llm = self._build_llm_context(
            query, agent_results, knowledge_context,
        )

        elapsed = (time.perf_counter() - start) * 1000

        logger.info(
            "Orchestrator completed in %.1fms: %d agents, %d tool calls.",
            elapsed,
            len(agent_results),
            len(all_tool_calls),
        )

        return OrchestratorResult(
            agent_results=agent_results,
            all_tool_calls=all_tool_calls,
            knowledge_context=knowledge_context,
            context_for_llm=context_for_llm,
            agents_used=[a.agent_name for a in agent_results],
            total_time_ms=round(elapsed, 1),
        )

    def _build_context(
        self,
        query: str,
        user_context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Build context dict from the query and user context."""
        ctx: dict[str, Any] = dict(user_context or {})

        # Extract player names
        if "player_names" not in ctx:
            ctx["player_names"] = _extract_player_names(query)

        # Extract team name
        if "team_name" not in ctx:
            ctx["team_name"] = _extract_team_name(query)

        return ctx

    def _select_agents(
        self,
        query: str,
        max_agents: int = 3,
    ) -> list[BaseAgent]:
        """Select the most relevant agents for a query.

        Args:
            query: The user's message.
            max_agents: Maximum number of agents to invoke.

        Returns:
            List of selected agents, ordered by relevance.
        """
        scored = [
            (agent, agent.can_handle(query))
            for agent in self._agents
        ]

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        # Select agents with score > 0, up to max
        selected = [
            agent for agent, score in scored
            if score > 0.0
        ][:max_agents]

        # If nothing matched, default to research agent
        if not selected:
            research = next(
                (a for a in self._agents if a.name == "research"),
                self._agents[0],
            )
            selected = [research]

        return selected

    def _build_llm_context(
        self,
        query: str,
        agent_results: list[AgentResult],
        knowledge_context: dict[str, Any] | None,
    ) -> str:
        """Build a structured context string for the LLM.

        This is injected into the LLM prompt so it can generate
        a grounded, evidence-based response.

        Args:
            query: The user's original query.
            agent_results: Results from all invoked agents.
            knowledge_context: Any RAG knowledge retrieved.

        Returns:
            Formatted context string.
        """
        parts: list[str] = []

        parts.append("=== AGENT ANALYSIS RESULTS ===\n")

        for result in agent_results:
            parts.append(f"--- Agent: {result.agent_name} ---")
            if result.summary:
                parts.append(f"Summary: {result.summary}")

            # Include analysis data (compacted)
            import json
            try:
                analysis_str = json.dumps(
                    result.analysis, default=str, indent=None,
                )
                # Truncate very long analysis to avoid overwhelming the LLM
                if len(analysis_str) > 4000:
                    analysis_str = analysis_str[:4000] + "... [truncated]"
                parts.append(f"Data: {analysis_str}")
            except (TypeError, ValueError):
                parts.append("Data: [serialization error]")

            parts.append("")

        if knowledge_context and knowledge_context.get("has_knowledge"):
            parts.append("=== KNOWLEDGE BASE (Static FPL Rules/Strategy) ===")
            parts.append(
                "NOTE: This is curated knowledge, NOT live player data. "
                "Use it for rules and strategy context only."
            )
            for chunk in knowledge_context.get("chunks", []):
                parts.append(
                    f"[{chunk.get('title', 'Unknown')}]: "
                    f"{chunk.get('text', '')[:500]}"
                )
            parts.append("")

        parts.append("=== END ANALYSIS ===")
        parts.append(
            "Use the above data to answer the user's question. "
            "NEVER invent statistics, availability, or predictions "
            "not present in the data above. If data is missing, "
            "say so explicitly."
        )

        return "\n".join(parts)
