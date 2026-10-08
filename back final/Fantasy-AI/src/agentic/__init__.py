"""Agentic AI system for Fantasy AI.

This package implements a production-quality agentic architecture
consisting of:

- **Tool Layer**: Well-defined, schema-validated tools wrapping existing
  Fantasy AI services.
- **RAG Pipeline**: Retrieval-augmented generation for FPL rules and
  strategy knowledge.
- **Specialized Agents**: Domain-specific reasoning agents (squad,
  player, fixture, news, strategy, research).
- **Orchestrator**: Routes user requests to appropriate agents and
  tools, coordinates multi-agent responses.
- **MCP Server**: Model Context Protocol server exposing fantasy tools
  for external consumption.
"""
