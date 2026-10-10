"""Router: POST /chatbot/message.

Provides the API endpoint for the AI chatbot assistant.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.config.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/chatbot", tags=["chatbot"])


class ChatMessage(BaseModel):
    """A single message in the conversation."""

    role: str = Field(description="Message role: 'user' or 'assistant'")
    content: str = Field(description="Message text content")


class ChatRequest(BaseModel):
    """Request payload for the chatbot endpoint."""

    message: str = Field(
        description="The user's message to the chatbot.",
        min_length=1,
        max_length=2000,
    )
    conversation_history: list[ChatMessage] = Field(
        default_factory=list,
        description="Prior conversation messages for context.",
        max_length=40,
    )


class ChatResponse(BaseModel):
    """Response from the chatbot."""

    response: str = Field(description="The assistant's response text.")
    tool_calls: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Tools that were called during this turn.",
    )
    conversation: list[ChatMessage] = Field(
        default_factory=list,
        description="Updated conversation history including this turn.",
    )
    provider: str | None = Field(
        default=None,
        description="Provider that handled the response (gemini/openai/fallback).",
    )
    model: str | None = Field(
        default=None,
        description="Model name used for generating the response.",
    )
    fallback: bool = Field(
        default=False,
        description="Whether fallback mode was used.",
    )
    fallback_reason: str | None = Field(
        default=None,
        description="Reason fallback mode was invoked, if applicable.",
    )


class ChatStatusResponse(BaseModel):
    """Chatbot availability status."""

    enabled: bool = Field(description="Whether the chatbot feature is enabled.")
    configured: bool = Field(
        description="Whether an LLM API key is configured."
    )
    provider: str | None = Field(
        default=None,
        description="The configured LLM provider (gemini/openai).",
    )
    model: str | None = Field(
        default=None,
        description="The configured LLM model name.",
    )


@router.get("/status", response_model=ChatStatusResponse)
def chatbot_status(request: Request) -> ChatStatusResponse:
    """Check whether the chatbot is enabled and configured.

    Returns:
        ChatStatusResponse: Current chatbot availability.
    """
    app_state = getattr(request.app.state, "fantasy_ai_state", None)
    if app_state is None:
        return ChatStatusResponse(enabled=False, configured=False)

    settings = app_state.settings
    chatbot_settings = getattr(settings, "chatbot", None)

    if chatbot_settings is None or not getattr(chatbot_settings, "enabled", False):
        return ChatStatusResponse(enabled=False, configured=False)

    api_key = getattr(chatbot_settings, "llm_api_key", "")

    return ChatStatusResponse(
        enabled=True,
        configured=bool(api_key),
        provider=getattr(chatbot_settings, "llm_provider", None),
        model=getattr(chatbot_settings, "llm_model", None),
    )


@router.post("/message", response_model=ChatResponse)
async def chat_message(
    request: Request,
    payload: ChatRequest,
) -> ChatResponse:
    """Process a chatbot message with tool-augmented LLM.

    The chatbot retrieves data from the Fantasy AI prediction system
    using tools — it never invents current player information.

    Args:
        request: The current request.
        payload: The chat request with message and optional history.

    Returns:
        ChatResponse: The assistant's response, tool calls made,
        and updated conversation history.

    Raises:
        HTTPException: 503 if the chatbot is not available.
    """
    app_state = getattr(request.app.state, "fantasy_ai_state", None)
    if app_state is None:
        raise HTTPException(
            status_code=503,
            detail="Prediction data is not available. The chatbot requires a loaded application state.",
        )

    settings = app_state.settings
    chatbot_settings = getattr(settings, "chatbot", None)

    if chatbot_settings is None:
        raise HTTPException(
            status_code=503,
            detail="Chatbot is not configured. Set FANTASY_AI_CHATBOT_ENABLED=true and provide an API key.",
        )

    if not getattr(chatbot_settings, "enabled", False):
        raise HTTPException(
            status_code=503,
            detail="Chatbot feature is disabled. Set FANTASY_AI_CHATBOT_ENABLED=true.",
        )

    # Lazy-import to avoid startup cost
    from src.chatbot.service import ChatbotService

    service = ChatbotService(
        app_state,
        provider=getattr(chatbot_settings, "llm_provider", "gemini"),
        api_key=getattr(chatbot_settings, "llm_api_key", ""),
        model=getattr(chatbot_settings, "llm_model", "gemini-3.8-flash"),
        max_tool_calls=getattr(chatbot_settings, "max_tool_calls_per_turn", 5),
    )

    history = [
        {"role": msg.role, "content": msg.content}
        for msg in payload.conversation_history
    ]

    logger.info(
        "Chatbot request: message_length=%d, history_length=%d",
        len(payload.message),
        len(history),
    )

    result = await service.chat(
        user_message=payload.message,
        conversation_history=history,
    )

    return ChatResponse(
        response=result.get("response", ""),
        tool_calls=result.get("tool_calls", []),
        conversation=[
            ChatMessage(role=m["role"], content=m["content"])
            for m in result.get("conversation", [])
        ],
        provider=result.get("provider", "fallback" if result.get("fallback") else getattr(chatbot_settings, "llm_provider", "gemini")),
        model=result.get("model"),
        fallback=result.get("fallback", False),
        fallback_reason=result.get("fallback_reason"),
    )
