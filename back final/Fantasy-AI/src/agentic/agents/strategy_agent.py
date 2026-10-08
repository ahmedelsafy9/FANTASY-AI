"""Strategy Agent.

Responsible for:
- Transfer strategy (when to hold, sell, buy)
- Captaincy strategy
- Chip timing (wildcard, free hit, bench boost, triple captain)
- Risk/reward evaluation
- Short-term vs long-term decisions
"""

from __future__ import annotations

from typing import Any

from src.agentic.agents.base import AgentResult, BaseAgent
from src.agentic.rag.retriever import KnowledgeRetriever
from src.config.logging_config import get_logger

logger = get_logger(__name__)


class StrategyAgent(BaseAgent):
    """Provides strategic FPL advice grounded in knowledge and data."""

    def __init__(self, tool_registry, retriever: KnowledgeRetriever) -> None:
        super().__init__(tool_registry)
        self._retriever = retriever

    @property
    def name(self) -> str:
        return "strategy"

    @property
    def description(self) -> str:
        return (
            "Provides strategic FPL advice: transfers, captaincy, chips, "
            "risk/reward, and short-term vs long-term decisions."
        )

    @property
    def tool_names(self) -> list[str]:
        return [
            "get_captain_recommendation",
            "get_gameweek_predictions",
            "get_differential_picks",
            "get_current_gameweek",
            "analyze_squad",
        ]

    @property
    def relevance_keywords(self) -> list[str]:
        return [
            "strategy", "should i", "worth", "advice",
            "wildcard", "free hit", "bench boost", "triple captain",
            "chip", "wc", "bb", "tc", "fh",
            "plan", "long term", "short term",
            "differential", "template", "risk",
            "hold", "keep", "sell", "when to",
        ]

    def analyze(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        """Provide strategic advice combining knowledge and live data."""
        tool_calls: list[dict[str, Any]] = []
        analysis: dict[str, Any] = {}
        lower = query.lower()

        # Retrieve relevant strategy knowledge
        knowledge = self._retriever.retrieve_as_context(query, top_k=3)
        if knowledge.get("has_knowledge"):
            analysis["strategy_knowledge"] = knowledge

        # Chip-related questions
        if any(kw in lower for kw in (
            "wildcard", "free hit", "bench boost", "triple captain",
            "chip", "wc", "bb", "tc", "fh",
        )):
            gw_result = self._call_tool("get_current_gameweek")
            tool_calls.append({
                "tool": "get_current_gameweek",
                "success": gw_result.success,
            })
            if gw_result.success:
                analysis["gameweek_context"] = gw_result.data

        # Differential strategy
        if any(kw in lower for kw in ("differential", "low ownership", "punt")):
            result = self._call_tool(
                "get_differential_picks",
                limit=5,
            )
            tool_calls.append({
                "tool": "get_differential_picks",
                "success": result.success,
            })
            if result.success:
                analysis["differential_picks"] = result.data

        # Captain strategy
        if any(kw in lower for kw in ("captain", "captaincy", "armband")):
            result = self._call_tool("get_captain_recommendation")
            tool_calls.append({
                "tool": "get_captain_recommendation",
                "success": result.success,
            })
            if result.success:
                analysis["captain_recommendation"] = result.data

        # General predictions for context
        if not analysis.get("captain_recommendation") and not analysis.get("differential_picks"):
            result = self._call_tool(
                "get_gameweek_predictions",
                limit=10,
            )
            tool_calls.append({
                "tool": "get_gameweek_predictions",
                "success": result.success,
            })
            if result.success:
                analysis["predictions_context"] = result.data

        return AgentResult(
            agent_name=self.name,
            analysis=analysis,
            tool_calls=tool_calls,
            knowledge_context=knowledge if knowledge.get("has_knowledge") else None,
            summary="Strategy analysis completed with knowledge context.",
        )
