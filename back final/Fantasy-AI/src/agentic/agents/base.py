"""Base agent class for the specialized agent system.

Each agent has:
- A name and description
- A list of tools it is authorized to use
- An ``can_handle(query)`` method to determine relevance
- An ``analyze(query, context)`` method that gathers data and returns
  structured analysis results

Agents do NOT call the LLM themselves — they gather and structure
data using tools, then return their analysis to the orchestrator
which passes everything to the LLM for final response generation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from src.agentic.tools.base import ToolResult
from src.agentic.tools.registry import ToolRegistry
from src.config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class Finding:
    """A single structured finding from an agent's investigation.

    Attributes:
        factor: Domain factor ('availability', 'fixtures', 'form', 'predictions', 'risk', 'strategy', 'rules').
        player: Optional player name if finding is player-specific.
        assessment: Qualitative evaluation ('favorable', 'unfavorable', 'neutral', 'doubtful', 'warning').
        evidence: Raw data metrics supporting the assessment.
        summary: Clear human-readable summary of the finding.
    """

    factor: str
    player: str | None = None
    assessment: str = "neutral"
    evidence: dict[str, Any] = field(default_factory=dict)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "factor": self.factor,
            "player": self.player,
            "assessment": self.assessment,
            "evidence": self.evidence,
            "summary": self.summary,
        }


@dataclass
class AgentResult:
    """Structured result from an agent's analysis.

    Attributes:
        agent_name: Which agent produced this result.
        status: Execution status ('success', 'partial', 'failed').
        findings: Structured findings across domain factors.
        analysis: Raw data dictionary.
        tool_calls: Tools that were called and their results.
        knowledge_context: Any RAG knowledge retrieved.
        confidence: Statistically calculated confidence (0–1), or None if not calculated.
        sources: List of data or knowledge sources used.
        summary: Short summary of what was found.
    """

    agent_name: str
    status: str = "success"
    findings: list[Finding] = field(default_factory=list)
    analysis: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    knowledge_context: dict[str, Any] | None = None
    confidence: float | None = None
    sources: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-safe dict for LLM consumption and reporting."""
        result: dict[str, Any] = {
            "agent": self.agent_name,
            "status": self.status,
            "confidence": self.confidence,
            "summary": self.summary,
            "findings": [f.to_dict() if isinstance(f, Finding) else f for f in self.findings],
            "analysis": self.analysis,
            "sources": self.sources,
        }
        if self.tool_calls:
            result["tools_used"] = [
                {"tool": tc.get("tool"), "success": tc.get("success", True)}
                for tc in self.tool_calls
            ]
        if self.knowledge_context and self.knowledge_context.get("has_knowledge"):
            result["knowledge"] = self.knowledge_context
        return result


class BaseAgent(ABC):
    """Abstract base class for specialized agents.

    Subclasses must implement:
    - ``name`` — unique agent identifier
    - ``description`` — what this agent does
    - ``tool_names`` — which tools this agent can use
    - ``relevance_keywords`` — keywords that trigger this agent
    - ``analyze(query, context)`` — gather data and return analysis
    """

    def __init__(self, tool_registry: ToolRegistry) -> None:
        self._registry = tool_registry

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique agent identifier."""

    @property
    @abstractmethod
    def description(self) -> str:
        """What this agent does."""

    @property
    @abstractmethod
    def tool_names(self) -> list[str]:
        """Tools this agent is authorized to use."""

    @property
    @abstractmethod
    def relevance_keywords(self) -> list[str]:
        """Keywords that suggest this agent is relevant."""

    def can_handle(self, query: str) -> float:
        """Score how relevant this agent is for a query (0–1).

        Higher score = more relevant.  The orchestrator uses this
        to decide which agents to invoke.

        Args:
            query: The user's message.

        Returns:
            Relevance score between 0.0 and 1.0.
        """
        lower = query.lower()
        hits = sum(1 for kw in self.relevance_keywords if kw in lower)
        if hits == 0:
            return 0.0
        # Normalize: more keyword hits = higher relevance, capped at 1.0
        return min(1.0, hits * 0.25)

    def _call_tool(self, tool_name: str, **kwargs: Any) -> ToolResult:
        """Call a tool from this agent's authorized set.

        Args:
            tool_name: Name of the tool to call.
            **kwargs: Tool arguments.

        Returns:
            The tool's result.
        """
        if tool_name not in self.tool_names:
            logger.warning(
                "Agent '%s' attempted to call unauthorized tool '%s'",
                self.name,
                tool_name,
            )
            return ToolResult(
                success=False,
                data=None,
                error=f"Tool '{tool_name}' is not authorized for agent '{self.name}'",
                tool_name=tool_name,
            )
        return self._registry.execute(tool_name, **kwargs)

    @abstractmethod
    def analyze(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        """Gather data and produce structured analysis.

        Args:
            query: The user's message.
            context: Optional additional context (e.g., squad, history).

        Returns:
            An :class:`AgentResult` with structured analysis.
        """
