"""Base tool abstraction for the agentic system.

Every tool the agent can call inherits from :class:`BaseTool`.  Tools
are thin, validated wrappers around existing Fantasy AI services — they
never introduce new data sources or bypass existing business logic.

Each tool declares:
- A unique ``name``
- A human-readable ``description`` (for the LLM)
- A JSON-schema ``parameters`` spec
- A type-safe ``execute(**kwargs)`` method
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from src.config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ToolParameter:
    """Schema for a single tool parameter."""

    name: str
    type: str  # "string", "integer", "number", "boolean"
    description: str
    required: bool = True
    enum: list[str] | None = None
    default: Any = None


@dataclass(frozen=True)
class ToolResult:
    """Structured result from a tool execution.

    Attributes:
        success: Whether the tool executed without error.
        data: The tool's output data (JSON-serialisable).
        error: Error message if the tool failed.
        execution_time_ms: Wall-clock time in milliseconds.
        tool_name: Name of the tool that produced this result.
        source: Where the data came from (e.g. "live_fpl", "knowledge_base").
    """

    success: bool
    data: Any
    error: str | None = None
    execution_time_ms: float = 0.0
    tool_name: str = ""
    source: str = "live_data"

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-safe dictionary."""
        result: dict[str, Any] = {
            "success": self.success,
            "tool_name": self.tool_name,
            "source": self.source,
        }
        if self.success:
            result["data"] = self.data
        else:
            result["error"] = self.error
        return result


class BaseTool(ABC):
    """Abstract base for all agent tools.

    Subclasses must implement:
    - ``name`` property
    - ``description`` property
    - ``parameters`` property
    - ``_execute(**kwargs)`` method

    The public ``execute()`` method wraps ``_execute()`` with input
    validation, structured error handling, and execution timing.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool identifier."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description for the LLM."""

    @property
    @abstractmethod
    def parameters(self) -> list[ToolParameter]:
        """Ordered list of tool parameters."""

    @abstractmethod
    def _execute(self, **kwargs: Any) -> Any:
        """Execute the tool's core logic.

        Returns:
            JSON-serialisable result data.

        Raises:
            Any exception — caught by the public ``execute`` wrapper.
        """

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with validation, timing, and error handling.

        Args:
            **kwargs: Tool arguments matching the ``parameters`` schema.

        Returns:
            A :class:`ToolResult` with structured output.
        """
        # Validate required parameters
        for param in self.parameters:
            if param.required and param.name not in kwargs:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Missing required parameter: '{param.name}'",
                    tool_name=self.name,
                )

        # Apply defaults
        for param in self.parameters:
            if param.name not in kwargs and param.default is not None:
                kwargs[param.name] = param.default

        start = time.perf_counter()
        try:
            data = self._execute(**kwargs)
            elapsed = (time.perf_counter() - start) * 1000

            logger.info(
                "Tool '%s' executed successfully in %.1fms",
                self.name,
                elapsed,
            )

            return ToolResult(
                success=True,
                data=data,
                execution_time_ms=round(elapsed, 1),
                tool_name=self.name,
                source="live_data",
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.exception(
                "Tool '%s' failed after %.1fms: %s",
                self.name,
                elapsed,
                exc,
            )
            return ToolResult(
                success=False,
                data=None,
                error=f"Tool execution failed: {exc}",
                execution_time_ms=round(elapsed, 1),
                tool_name=self.name,
            )

    def to_schema(self) -> dict[str, Any]:
        """Export as a JSON-schema dict suitable for LLM function calling.

        Returns:
            Dict matching the OpenAI/Gemini function-calling schema format.
        """
        properties: dict[str, Any] = {}
        required: list[str] = []

        for param in self.parameters:
            prop: dict[str, Any] = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            properties[param.name] = prop
            if param.required:
                required.append(param.name)

        schema: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
            },
        }
        if required:
            schema["parameters"]["required"] = required

        return schema
