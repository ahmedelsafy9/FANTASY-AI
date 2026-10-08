"""Tool registry: central catalogue of all available agent tools.

The registry provides:
- Tool registration and lookup by name
- Bulk schema export for LLM function calling
- Tool discovery for the orchestrator and MCP server
"""

from __future__ import annotations

from typing import Any

from src.agentic.tools.base import BaseTool, ToolResult
from src.config.logging_config import get_logger

logger = get_logger(__name__)


class ToolRegistry:
    """Central registry holding all agent-callable tools.

    Tools are registered at startup and looked up by name during
    agent execution.  The registry is the single source of truth
    for what tools exist.
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool.

        Args:
            tool: The tool instance to register.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        if tool.name in self._tools:
            raise ValueError(
                f"Tool '{tool.name}' is already registered."
            )
        self._tools[tool.name] = tool
        logger.debug("Registered tool: %s", tool.name)

    def get(self, name: str) -> BaseTool | None:
        """Look up a tool by name.

        Args:
            name: The tool's unique identifier.

        Returns:
            The tool instance, or ``None`` if not found.
        """
        return self._tools.get(name)

    def execute(self, name: str, **kwargs: Any) -> ToolResult:
        """Execute a tool by name.

        Args:
            name: The tool's unique identifier.
            **kwargs: Arguments to pass to the tool.

        Returns:
            A :class:`ToolResult` (error result if tool not found).
        """
        tool = self.get(name)
        if tool is None:
            logger.warning("Attempted to execute unknown tool: %s", name)
            return ToolResult(
                success=False,
                data=None,
                error=f"Unknown tool: '{name}'",
                tool_name=name,
            )
        return tool.execute(**kwargs)

    def list_tools(self) -> list[str]:
        """Return all registered tool names.

        Returns:
            Sorted list of tool names.
        """
        return sorted(self._tools.keys())

    def get_all_schemas(self) -> list[dict[str, Any]]:
        """Export every tool's JSON schema for LLM function calling.

        Returns:
            List of tool schema dicts.
        """
        return [
            tool.to_schema()
            for tool in self._tools.values()
        ]

    def get_tools_for_agent(self, tool_names: list[str]) -> list[BaseTool]:
        """Return tool instances for a list of names.

        Args:
            tool_names: Names of tools to retrieve.

        Returns:
            List of matching tool instances (skips unknown names).
        """
        tools = []
        for name in tool_names:
            tool = self.get(name)
            if tool:
                tools.append(tool)
            else:
                logger.warning(
                    "Agent requested unknown tool '%s' — skipping.", name
                )
        return tools

    @property
    def count(self) -> int:
        """Number of registered tools."""
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)
