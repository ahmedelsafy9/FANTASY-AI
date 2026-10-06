"""Chatbot service: orchestrates LLM interaction with tool calling.

Supports Google Gemini (primary) and OpenAI (fallback) as LLM providers.
The service manages conversation context, tool dispatch, and response
generation.

Architecture:
  User message → ChatbotService → LLM with tool definitions
                                     ↓
                              Tool call requested?
                              ├── Yes → Execute tool → Feed result back → LLM generates response
                              └── No  → LLM generates response directly
                                     ↓
                     Fallback rules when LLM key is absent or API fails
"""

from __future__ import annotations

import json
import re
from typing import Any

import pandas as pd

from src.api.state import AppState
from src.chatbot.player_resolver import PlayerResolver
from src.chatbot.prompts import build_system_prompt
from src.chatbot.tools import TOOL_DEFINITIONS, ChatbotTools
from src.config.logging_config import get_logger

logger = get_logger(__name__)


def _normalize_arabic(text: str) -> str:
    """Normalize Arabic text by removing tashkeel and unifying letter variants."""
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text)
    text = re.sub(r"[أإآٱ]", "ا", text)
    text = re.sub(r"ة", "ه", text)
    text = re.sub(r"ى", "ي", text)
    return text.strip().lower()


def _is_arabic(text: str) -> bool:
    """Check if string contains Arabic characters."""
    return bool(re.search(r"[\u0600-\u06FF]", text))


def _make_json_safe(obj: Any) -> Any:
    """Recursively convert any pandas, numpy, or special object to JSON-safe primitives."""
    if obj is None:
        return None
    if isinstance(obj, (bool, str, int)):
        return obj
    if isinstance(obj, float):
        if pd.isna(obj) or obj != obj:
            return None
        return obj
    if hasattr(obj, "item"):
        try:
            val = obj.item()
            return _make_json_safe(val)
        except Exception:
            return str(obj)
    if hasattr(obj, "to_dict"):
        try:
            return _make_json_safe(obj.to_dict())
        except Exception:
            pass
    if isinstance(obj, dict):
        return {str(k): _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_make_json_safe(v) for v in obj]
    try:
        if pd.isna(obj):
            return None
    except Exception:
        pass
    return str(obj)


def sanitize_conversation_history(
    history: list[dict[str, Any]] | None,
) -> list[dict[str, str]]:
    """Clean and validate conversation history messages.

    - Ensures only 'user' and 'assistant' roles are retained.
    - Strips empty or whitespace-only messages.
    - Removes internal error messages from history.
    """
    if not history:
        return []

    cleaned: list[dict[str, str]] = []
    for msg in history:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role", "")).strip().lower()
        content = str(msg.get("content", "")).strip()

        if role not in ("user", "assistant"):
            continue
        if not content:
            continue
        # Drop client-side connection/error placeholders
        if content.startswith("Sorry, I couldn't") or content.startswith("Unable to connect"):
            continue

        cleaned.append({"role": role, "content": content})

    return cleaned


class ChatbotService:
    """Orchestrates chatbot interactions using tool-augmented LLM.

    Args:
        app_state: The shared application state.
        provider: LLM provider ("gemini" or "openai").
        api_key: API key for the LLM provider.
        model: Model name to use.
        max_tool_calls: Maximum tool calls per conversation turn.
    """

    def __init__(
        self,
        app_state: AppState,
        *,
        provider: str = "gemini",
        api_key: str = "",
        model: str = "gemini-2.5-flash",
        max_tool_calls: int = 5,
    ) -> None:
        self._state = app_state
        self._provider = provider.lower()
        self._api_key = api_key.strip()
        self._model = model
        self._max_tool_calls = max_tool_calls
        self._tools = ChatbotTools(app_state)
        self._system_prompt = build_system_prompt(
            season=app_state.season,
            predicted_gameweek=app_state.predicted_gameweek,
            latest_completed_gameweek=app_state.latest_completed_gameweek,
            generated_at=app_state.generated_at,
            player_count=len(app_state.predictions),
            scoring_model=getattr(app_state, "scoring_model", "unknown"),
        )

    @property
    def is_configured(self) -> bool:
        """Whether the chatbot has a valid API key configured."""
        return bool(self._api_key)

    async def chat(
        self,
        user_message: str,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Process a user message and return the assistant's response.

        Args:
            user_message: The user's message text.
            conversation_history: Optional list of prior messages,
                each with "role" ("user"/"assistant") and "content".

        Returns:
            Dict with "response" (str), "tool_calls" (list), and
            "conversation" (updated history).
        """
        history = sanitize_conversation_history(conversation_history)

        logger.info(
            "ChatbotService.chat starting: provider=%s, model=%s, has_api_key=%s, "
            "message_len=%d, history_turns=%d",
            self._provider,
            self._model,
            self.is_configured,
            len(user_message),
            len(history),
        )

        if not self.is_configured:
            logger.info("No API key configured for provider '%s'. Using expert fallback.", self._provider)
            return self._fallback_response(user_message, conversation_history=history)

        if self._provider == "gemini":
            return await self._chat_gemini(user_message, history)
        elif self._provider == "openai":
            return await self._chat_openai(user_message, history)
        else:
            logger.warning("Unknown LLM provider '%s'. Using fallback.", self._provider)
            return self._fallback_response(user_message, conversation_history=history)

    def _execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Dispatch a tool call to the appropriate executor safely.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Tool arguments.

        Returns:
            JSON-serialisable tool result.
        """
        tool_map = {
            "search_player_by_name": self._tools.search_player_by_name,
            "get_player_info": self._tools.get_player_info,
            "get_player_availability": self._tools.get_player_availability,
            "get_gameweek_predictions": self._tools.get_gameweek_predictions,
            "compare_players": self._tools.compare_players,
            "get_captain_recommendation": self._tools.get_captain_recommendation,
            "get_current_gameweek": self._tools.get_current_gameweek,
            "get_team_players": self._tools.get_team_players,
            "get_fixture_info": self._tools.get_fixture_info,
            "get_top_by_position": self._tools.get_top_by_position,
            "get_differential_picks": self._tools.get_differential_picks,
            "get_injured_doubtful_players": self._tools.get_injured_doubtful_players,
        }

        executor = tool_map.get(tool_name)
        if executor is None:
            logger.warning("Tool not found: %s", tool_name)
            return {"error": f"Unknown tool: {tool_name}"}

        logger.info("Executing tool: %s with args: %s", tool_name, json.dumps(arguments, default=str)[:300])

        try:
            raw_result = executor(**arguments)
            safe_result = _make_json_safe(raw_result)
            logger.info("Tool %s executed successfully.", tool_name)
            return safe_result
        except Exception as exc:
            logger.exception("Tool execution error (%s): %s", tool_name, exc)
            return {"error": f"Tool execution failed: {exc}"}

    # ---------------------------------------------------------------
    # Gemini implementation
    # ---------------------------------------------------------------

    async def _chat_gemini(
        self,
        user_message: str,
        history: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Chat using the Google Gemini API with function calling."""
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            logger.error("google-genai package not installed. Falling back to rule-based engine.")
            return self._fallback_response(user_message, conversation_history=history)

        try:
            client = genai.Client(api_key=self._api_key)

            # Build Gemini tool declarations
            function_declarations = []
            for tool_def in TOOL_DEFINITIONS:
                params = tool_def.get("parameters", {})
                fd = types.FunctionDeclaration(
                    name=tool_def["name"],
                    description=tool_def["description"],
                    parameters=params if params.get("properties") else None,
                )
                function_declarations.append(fd)

            gemini_tools = [types.Tool(function_declarations=function_declarations)]

            # Build message history
            contents: list[types.Content] = []
            for msg in history:
                role = "user" if msg["role"] == "user" else "model"
                contents.append(
                    types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=msg["content"])],
                    )
                )

            # Add current user message
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=user_message)],
                )
            )

            tool_calls_made: list[dict[str, Any]] = []
            iteration = 0

            while iteration < self._max_tool_calls:
                iteration += 1

                logger.info(
                    "Calling Gemini model '%s' (iteration %d/%d)...",
                    self._model,
                    iteration,
                    self._max_tool_calls,
                )

                response = client.models.generate_content(
                    model=self._model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=self._system_prompt,
                        tools=gemini_tools,
                        temperature=0.7,
                    ),
                )

                # Check if the response contains function calls
                if (
                    response.candidates
                    and response.candidates[0].content
                    and response.candidates[0].content.parts
                ):
                    parts = response.candidates[0].content.parts
                    has_function_call = any(part.function_call for part in parts)

                    if has_function_call:
                        # Append the model's function-calling turn to history
                        contents.append(response.candidates[0].content)

                        function_response_parts = []
                        for part in parts:
                            if part.function_call:
                                fc = part.function_call
                                args = dict(fc.args) if fc.args else {}

                                logger.info(
                                    "Gemini requested tool call: %s(args=%s)",
                                    fc.name,
                                    json.dumps(args, default=str)[:200],
                                )

                                result = self._execute_tool(fc.name, args)
                                tool_calls_made.append({
                                    "tool": fc.name,
                                    "args": args,
                                })

                                function_response_parts.append(
                                    types.Part.from_function_response(
                                        name=fc.name,
                                        response={"result": result},
                                    )
                                )

                        # Feed function execution results back to the model as user turn
                        contents.append(
                            types.Content(
                                role="user",
                                parts=function_response_parts,
                            )
                        )
                        continue  # Let Gemini interpret the tool outputs

                # No more function calls
                break

            # Extract final text response safely
            response_text = ""
            try:
                if response.text:
                    response_text = response.text
            except Exception:
                pass

            if not response_text and response.candidates and response.candidates[0].content:
                parts = response.candidates[0].content.parts or []
                text_parts = [part.text for part in parts if hasattr(part, "text") and part.text]
                if text_parts:
                    response_text = "\n".join(text_parts)

            if not response_text.strip():
                logger.warning("Gemini returned empty text response. Falling back.")
                return self._fallback_response(user_message, conversation_history=history)

            updated_history = list(history)
            updated_history.append({"role": "user", "content": user_message})
            updated_history.append({"role": "assistant", "content": response_text})

            logger.info(
                "Gemini response generated successfully: response_len=%d, tools_used=%d",
                len(response_text),
                len(tool_calls_made),
            )

            return {
                "response": response_text,
                "tool_calls": tool_calls_made,
                "conversation": updated_history,
            }

        except Exception as exc:
            logger.exception("Gemini API call failed (%s): %s. Using expert fallback.", type(exc).__name__, exc)
            return self._fallback_response(user_message, conversation_history=history)

    # ---------------------------------------------------------------
    # OpenAI implementation
    # ---------------------------------------------------------------

    async def _chat_openai(
        self,
        user_message: str,
        history: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Chat using the OpenAI API with function calling."""
        try:
            from openai import OpenAI
        except ImportError:
            logger.error("openai package not installed. Falling back to rule-based engine.")
            return self._fallback_response(user_message, conversation_history=history)

        try:
            client = OpenAI(api_key=self._api_key)

            # Build OpenAI tool declarations
            openai_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool_def["name"],
                        "description": tool_def["description"],
                        "parameters": tool_def["parameters"],
                    },
                }
                for tool_def in TOOL_DEFINITIONS
            ]

            messages: list[dict[str, Any]] = [
                {"role": "system", "content": self._system_prompt}
            ]
            for msg in history:
                messages.append({"role": msg["role"], "content": msg["content"]})
            messages.append({"role": "user", "content": user_message})

            tool_calls_made: list[dict[str, Any]] = []
            iteration = 0

            while iteration < self._max_tool_calls:
                iteration += 1

                completion = client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    tools=openai_tools,
                    temperature=0.7,
                )

                choice = completion.choices[0]

                if choice.message.tool_calls:
                    messages.append(choice.message.model_dump())

                    for tc in choice.message.tool_calls:
                        try:
                            args = json.loads(tc.function.arguments)
                        except json.JSONDecodeError:
                            args = {}

                        logger.info("OpenAI tool call: %s(%s)", tc.function.name, args)
                        result = self._execute_tool(tc.function.name, args)
                        tool_calls_made.append({
                            "tool": tc.function.name,
                            "args": args,
                        })

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(result, default=str),
                        })
                    continue

                break

            response_text = choice.message.content or ""
            if not response_text.strip():
                return self._fallback_response(user_message, conversation_history=history)

            updated_history = list(history)
            updated_history.append({"role": "user", "content": user_message})
            updated_history.append({"role": "assistant", "content": response_text})

            return {
                "response": response_text,
                "tool_calls": tool_calls_made,
                "conversation": updated_history,
            }

        except Exception as exc:
            logger.exception("OpenAI API call failed (%s): %s. Using expert fallback.", type(exc).__name__, exc)
            return self._fallback_response(user_message, conversation_history=history)

    # ---------------------------------------------------------------
    # Fallback (Offline / No API Key / Network Failure)
    # ---------------------------------------------------------------

    def _fallback_response(
        self,
        user_message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Generate a knowledgeable FPL analyst response using tools directly.

        Handles Arabic and English queries for captaincy, injuries, top players,
        differentials, and specific player inquiries without requiring an external LLM.
        """
        is_ar = _is_arabic(user_message)
        norm_ar = _normalize_arabic(user_message)
        lower = user_message.lower()

        logger.info(
            "Executing fallback response generator: query='%s', is_arabic=%s",
            user_message[:100],
            is_ar,
        )

        gw = self._state.predicted_gameweek or 6
        gw_str = f" {gw}"

        # ---------------------------------------------------------------
        # 1. Captaincy Intent
        # ---------------------------------------------------------------
        arabic_captain_keywords = (
            "كابتن", "الكابتن", "اكبتن", "أكبتن", "كبتن", "الكبتن",
            "كابتنه", "كابتنة", "الكابتنة", "كابتني", "شارة", "قائد", "القائد",
        )
        english_captain_keywords = (
            "captain", "captaincy", "armband", "who to c", "who should i c",
            "best captain", "vice captain", "vc",
        )

        is_captain = any(w in norm_ar for w in arabic_captain_keywords) or any(
            w in lower for w in english_captain_keywords
        )

        if is_captain:
            data = self._tools.get_captain_recommendation()
            candidates = data.get("candidates", [])

            if candidates:
                top = candidates[0]
                top_name = top.get("web_name") or top.get("name") or "اللاعب الأول"
                top_team = top.get("team") or ""
                top_pos = top.get("position") or ""
                pts = float(
                    top.get("predicted_expected_points")
                    or top.get("predicted_total_points")
                    or top.get("score_d")
                    or 0.0
                )
                opp = top.get("opponent_team")
                is_home = top.get("is_home")

                venue_ar = "داخل الأرض (H)" if is_home else "خارج الأرض (A)"
                venue_en = "Home" if is_home else "Away"
                fix_ar = f"ضد **{opp}** ({venue_ar})" if opp else "المباراة القادمة"
                fix_en = f"vs **{opp}** ({venue_en})" if opp else "Upcoming match"

                alt_candidates = candidates[1:4]
                alt_lines_ar = []
                alt_lines_en = []
                for alt in alt_candidates:
                    a_name = alt.get("web_name") or alt.get("name")
                    a_team = alt.get("team") or ""
                    a_pos = alt.get("position") or ""
                    a_pts = float(
                        alt.get("predicted_expected_points")
                        or alt.get("score_d")
                        or 0.0
                    )
                    a_opp = alt.get("opponent_team")
                    a_fix = f" (ضد {a_opp})" if a_opp else ""
                    a_fix_en = f" (vs {a_opp})" if a_opp else ""
                    alt_lines_ar.append(
                        f"• **{a_name}** ({a_team} - {a_pos}): متوقع **{a_pts:.1f}** نقطة{a_fix}"
                    )
                    alt_lines_en.append(
                        f"• **{a_name}** ({a_team} - {a_pos}): projected **{a_pts:.1f}** pts{a_fix_en}"
                    )

                if is_ar:
                    resp = (
                        f"بناءً على تحليلات ونموذج **Fantasy AI** للجولة{gw_str} "
                        f"(مع مراعاة الجاهزية الرسمية والدقائق المتوقعة):\n\n"
                        f"🏆 **أفضل خيار للكابتنة:** **{top_name}** ({top_team} - {top_pos})\n"
                        f"• **النقاط المتوقعة:** **{pts:.1f}** نقطة\n"
                        f"• **المواجهة:** {fix_ar}\n"
                        f"• **حالة الجاهزية:** جاهز للمشاركة وأساسي بنسبة 100% مع أمان تام في الدقائق.\n\n"
                    )
                    if alt_lines_ar:
                        resp += "⭐ **خيارات بديلة ممتازة:**\n" + "\n".join(alt_lines_ar) + "\n\n"
                    resp += (
                        f"💡 **نصيحة الكابتنة:** **{top_name}** يمتلك أعلى سقف وأرضية نقاط (Floor & Ceiling) "
                        f"لهذه الجولة، مما يجعله الخيار الأكثر أماناً واستقراراً لشارة القيادة."
                    )
                else:
                    resp = (
                        f"Based on **Fantasy AI** predictions for Gameweek{gw_str} "
                        f"(availability-adjusted):\n\n"
                        f"🏆 **Recommended Captain:** **{top_name}** ({top_team} - {top_pos})\n"
                        f"• **Projected Points:** **{pts:.1f}** pts\n"
                        f"• **Fixture:** {fix_en}\n"
                        f"• **Availability:** Fully fit starter with strong minutes security.\n\n"
                    )
                    if alt_lines_en:
                        resp += "⭐ **Alternative Candidates:**\n" + "\n".join(alt_lines_en) + "\n\n"
                    resp += (
                        f"💡 **Captaincy Tip:** **{top_name}** holds the highest projected points "
                        f"and lowest rotation risk for this gameweek. Recommended as the safest armband pick."
                    )

                updated_history = list(conversation_history or [])
                updated_history.append({"role": "user", "content": user_message})
                updated_history.append({"role": "assistant", "content": resp})

                return {
                    "response": resp,
                    "tool_calls": [{"tool": "get_captain_recommendation", "args": {}}],
                    "conversation": updated_history,
                }

        # ---------------------------------------------------------------
        # 2. Injuries / Doubts / Availability Intent
        # ---------------------------------------------------------------
        arabic_inj_keywords = (
            "مصاب", "اصاب", "إصاب", "المصابين", "مين المصابين",
            "غياب", "غيابات", "الغيابات", "شكوك", "مشكوك", "مش هيلعب", "موقوف",
        )
        english_inj_keywords = (
            "injur", "doubt", "ruled out", "suspended", "suspension",
            "availability", "who is out", "who is injured",
        )

        is_injury = any(w in norm_ar for w in arabic_inj_keywords) or any(
            w in lower for w in english_inj_keywords
        )

        if is_injury:
            data = self._tools.get_injured_doubtful_players()
            flagged = data.get("players", [])[:6]
            count = data.get("count", len(flagged))

            if is_ar:
                resp = f"🚨 **تقرير الإصابات والشكوك للجولة{gw_str} (يوجد {count} لاعب عليهم علامات):**\n\n"
                for p in flagged:
                    p_name = p.get("web_name") or p.get("name")
                    p_team = p.get("team", "")
                    p_status = p.get("availability_status", "مشكوك")
                    status_ar = {
                        "major_injury": "إصابة قوية (مستبعد)",
                        "minor_injury": "إصابة طفيفة",
                        "doubtful": "مشكوك في مشاركته",
                        "suspended": "إيقاف",
                        "unavailable": "غير متاح (انتقال/إعارة)",
                    }.get(p_status, "مشكوك في مشاركته")
                    news = p.get("team_news") or "لا توجد تفاصيل إضافية"
                    resp += f"• **{p_name}** ({p_team}): **{status_ar}** - *{news}*\n"
                resp += "\n💡 يُنصح بمتابعة المؤتمرات الصحفية قبل الموعد النهائي لتأكيد التشكيل."
            else:
                resp = f"🚨 **Key Injuries and Doubts for Gameweek{gw_str} ({count} players flagged):**\n\n"
                for p in flagged:
                    p_name = p.get("web_name") or p.get("name")
                    p_team = p.get("team", "")
                    p_status = p.get("availability_status", "doubtful").replace("_", " ").title()
                    news = p.get("team_news") or "No further news."
                    resp += f"• **{p_name}** ({p_team}): **{p_status}** - *{news}*\n"
                resp += "\n💡 Check official pre-match press conferences before the deadline."

            updated_history = list(conversation_history or [])
            updated_history.append({"role": "user", "content": user_message})
            updated_history.append({"role": "assistant", "content": resp})

            return {
                "response": resp,
                "tool_calls": [{"tool": "get_injured_doubtful_players", "args": {}}],
                "conversation": updated_history,
            }

        # ---------------------------------------------------------------
        # 3. Top Predicted Players Intent
        # ---------------------------------------------------------------
        arabic_top_keywords = (
            "افضل لاعب", "أفضل لاعب", "احسن لاعب", "أحسن لاعب",
            "مين افضل", "مين احسن", "اعلي نقاط", "أعلى نقاط", "توب", "ترشيحات",
        )
        english_top_keywords = (
            "top player", "best player", "highest predicted", "top pick", "best pick",
        )

        is_top = any(w in norm_ar for w in arabic_top_keywords) or any(
            w in lower for w in english_top_keywords
        )

        if is_top:
            data = self._tools.get_gameweek_predictions(limit=5)
            players = data.get("players", [])

            if is_ar:
                resp = f"🔥 **أعلى 5 لاعبين متوقعين للجولة{gw_str} (بناءً على نموذج Fantasy AI):**\n\n"
                for i, p in enumerate(players, 1):
                    p_name = p.get("web_name") or p.get("name")
                    p_team = p.get("team", "")
                    p_pos = p.get("position", "")
                    p_pts = float(p.get("predicted_expected_points") or p.get("score_d") or 0.0)
                    opp = p.get("opponent_team")
                    fix = f" (ضد {opp})" if opp else ""
                    resp += f"{i}. **{p_name}** ({p_team} - {p_pos}): **{p_pts:.1f}** نقطة متوقعة{fix}\n"
                resp += "\n💡 التوقعات تأخذ في الاعتبار صعوبة الخصم والجوانب التكتيكية ومعدل xG/xA الأخير."
            else:
                resp = f"🔥 **Top 5 Predicted Players for Gameweek{gw_str}:**\n\n"
                for i, p in enumerate(players, 1):
                    p_name = p.get("web_name") or p.get("name")
                    p_team = p.get("team", "")
                    p_pos = p.get("position", "")
                    p_pts = float(p.get("predicted_expected_points") or p.get("score_d") or 0.0)
                    opp = p.get("opponent_team")
                    fix = f" (vs {opp})" if opp else ""
                    resp += f"{i}. **{p_name}** ({p_team} - {p_pos}): **{p_pts:.1f}** predicted pts{fix}\n"
                resp += "\n💡 Projections factor in recent xG/xA form, minutes security, and fixture difficulty."

            updated_history = list(conversation_history or [])
            updated_history.append({"role": "user", "content": user_message})
            updated_history.append({"role": "assistant", "content": resp})

            return {
                "response": resp,
                "tool_calls": [{"tool": "get_gameweek_predictions", "args": {"limit": 5}}],
                "conversation": updated_history,
            }

        # ---------------------------------------------------------------
        # 4. Differentials Intent
        # ---------------------------------------------------------------
        arabic_diff_keywords = ("دفرنشل", "ديفرنشيل", "دفرنشال", "ديفرنشال", "مغمور", "ريسك")
        english_diff_keywords = ("differential", "differentials", "low ownership")

        is_diff = any(w in norm_ar for w in arabic_diff_keywords) or any(
            w in lower for w in english_diff_keywords
        )

        if is_diff:
            data = self._tools.get_differential_picks(limit=5)
            diffs = data.get("differentials", [])

            if is_ar:
                resp = f"💎 **أفضل خيارات الـ Differentials للجولة{gw_str} (نسبة امتلاك منخفضة مع سقف عالي):**\n\n"
                for p in diffs:
                    p_name = p.get("web_name") or p.get("name")
                    p_team = p.get("team", "")
                    p_pos = p.get("position", "")
                    p_pts = float(p.get("predicted_expected_points") or p.get("score_d") or 0.0)
                    own = float(p.get("selected_by_percent") or 0.0)
                    resp += f"• **{p_name}** ({p_team} - {p_pos}): متوقع **{p_pts:.1f}** نقطة (ملكية: {own:.1f}%)\n"
                resp += "\n💡 هذه الخيارات ممتازة لتعويض الفارق في الترتيب والمنافسة في الدوريات الخاصة."
            else:
                resp = f"💎 **Top Differential Picks for Gameweek{gw_str} (Low Ownership, High Upside):**\n\n"
                for p in diffs:
                    p_name = p.get("web_name") or p.get("name")
                    p_team = p.get("team", "")
                    p_pos = p.get("position", "")
                    p_pts = float(p.get("predicted_expected_points") or p.get("score_d") or 0.0)
                    own = float(p.get("selected_by_percent") or 0.0)
                    resp += f"• **{p_name}** ({p_team} - {p_pos}): **{p_pts:.1f}** proj pts (ownership: {own:.1f}%)\n"
                resp += "\n💡 Great picks for climbing ranks and gaining an edge in mini-leagues."

            updated_history = list(conversation_history or [])
            updated_history.append({"role": "user", "content": user_message})
            updated_history.append({"role": "assistant", "content": resp})

            return {
                "response": resp,
                "tool_calls": [{"tool": "get_differential_picks", "args": {"limit": 5}}],
                "conversation": updated_history,
            }

        # ---------------------------------------------------------------
        # 5. Specific Player Search Intent (e.g. "مين صلاح؟", "Palmer", "Haaland")
        # ---------------------------------------------------------------
        # Clean query from leading question words
        player_clean = re.sub(
            r"^(مين|هو|عن|معلومات عن|اخبار|أخبار|who is|tell me about|is)\s*",
            "",
            user_message,
            flags=re.IGNORECASE,
        ).strip("؟? .")

        if player_clean and len(player_clean) >= 2:
            matches = self._tools.search_player_by_name(player_clean)
            if matches:
                p = matches[0]
                p_name = p.get("web_name") or p.get("name")
                p_team = p.get("team", "")
                p_pos = p.get("position", "")
                p_price = float(p.get("value") or (p.get("now_cost", 0) / 10.0))
                p_pts = float(p.get("predicted_expected_points") or p.get("score_d") or 0.0)
                p_status = p.get("availability_status", "fit")
                p_news = p.get("team_news")
                opp = p.get("opponent_team")
                is_home = p.get("is_home")

                fix_str_ar = f"ضد {opp} ({'داخل الأرض' if is_home else 'خارج الأرض'})" if opp else "لا توجد مواجهة مسجلة"
                fix_str_en = f"vs {opp} ({'Home' if is_home else 'Away'})" if opp else "No upcoming fixture"

                status_map = {
                    "fit": "جاهز للمشاركة (Fit)",
                    "rotation_risk": "خطر التدوير (Rotation Risk)",
                    "doubtful": "مشكوك في مشاركته (Doubtful)",
                    "minor_injury": "إصابة طفيفة (Minor Injury)",
                    "major_injury": "مصاب (Injured)",
                    "suspended": "موقوف (Suspended)",
                    "unavailable": "غير متاح (Unavailable)",
                }
                status_desc = status_map.get(p_status, p_status)

                if is_ar:
                    resp = (
                        f"📊 **تقرير اللاعب:** **{p_name}** ({p_team} - {p_pos})\n\n"
                        f"• **السعر:** £{p_price:.1f}m\n"
                        f"• **النقاط المتوقعة للجولة{gw_str}:** **{p_pts:.1f}** نقطة\n"
                        f"• **المواجهة القادمة:** {fix_str_ar}\n"
                        f"• **حالة الجاهزية:** {status_desc}\n"
                    )
                    if p_news:
                        resp += f"• **آخر الأخبار الطبية:** {p_news}\n"
                else:
                    resp = (
                        f"📊 **Player Profile:** **{p_name}** ({p_team} - {p_pos})\n\n"
                        f"• **Price:** £{p_price:.1f}m\n"
                        f"• **Expected Points (GW{gw_str}):** **{p_pts:.1f}** pts\n"
                        f"• **Next Fixture:** {fix_str_en}\n"
                        f"• **Availability:** {p_status.replace('_', ' ').title()}\n"
                    )
                    if p_news:
                        resp += f"• **Team News:** {p_news}\n"

                updated_history = list(conversation_history or [])
                updated_history.append({"role": "user", "content": user_message})
                updated_history.append({"role": "assistant", "content": resp})

                return {
                    "response": resp,
                    "tool_calls": [{"tool": "get_player_info", "args": {"player_name": p_name}}],
                    "conversation": updated_history,
                }

        # ---------------------------------------------------------------
        # 6. Greetings Intent
        # ---------------------------------------------------------------
        arabic_greet_keywords = ("سلام", "اهلا", "أهلا", "مرحبا", "صباح الخير", "مساء الخير", "هاي", "هلا")
        english_greet_keywords = ("hello", "hi", "hey", "good morning", "good evening", "greetings")

        is_greet = any(w in norm_ar for w in arabic_greet_keywords) or any(
            w in lower for w in english_greet_keywords
        )

        if is_greet:
            if is_ar:
                resp = (
                    "أهلاً بك في **Fantasy AI Assistant**! ⚽🤖\n\n"
                    f"أنا محللك الذكي المتخصص في فانتازي الدوري الإنجليزي الممتاز (الجولة الحالية: GW{gw}).\n\n"
                    "يمكنك سؤالي عن:\n"
                    "• 🏆 **ترشيحات الكابتنة:** (مثال: *تفتكر اكبتن مين الجولة الجاية؟*)\n"
                    "• 🤕 **الإصابات والشكوك:** (مثال: *مين المصابين الأسبوع ده؟*)\n"
                    "• 🔥 **أعلى التوقعات:** (مثال: *مين أفضل لاعبين للجولة؟*)\n"
                    "• 💎 **الـ Differentials:** (مثال: *اقترح عليا differential picks*)\n"
                    "• 📊 **فحص أي لاعب:** (مثال: *مين صلاح؟* أو *هل بالمر جاهز؟*)"
                )
            else:
                resp = (
                    "Welcome to **Fantasy AI Assistant**! ⚽🤖\n\n"
                    f"I'm your expert Fantasy Premier League advisor (predicting Gameweek {gw}).\n\n"
                    "You can ask me about:\n"
                    "• 🏆 **Captain Picks:** (e.g. *Who should I captain this gameweek?*)\n"
                    "• 🤕 **Injuries & Team News:** (e.g. *Who is injured or doubtful?*)\n"
                    "• 🔥 **Top Predicted Players:** (e.g. *Who are the top projected players?*)\n"
                    "• 💎 **Differentials:** (e.g. *Give me differential picks*)\n"
                    "• 📊 **Player Analysis:** (e.g. *Tell me about Palmer* or *Is Saka fit?*)"
                )

            updated_history = list(conversation_history or [])
            updated_history.append({"role": "user", "content": user_message})
            updated_history.append({"role": "assistant", "content": resp})

            return {
                "response": resp,
                "tool_calls": [],
                "conversation": updated_history,
            }

        # ---------------------------------------------------------------
        # 7. General Fallback
        # ---------------------------------------------------------------
        if is_ar:
            resp = (
                f"أنا مساعدك الذكي في Fantasy AI للجولة{gw_str}! ⚽\n\n"
                "يمكنني مساعدتك مباشرة في:\n"
                "• 🏆 اختيار الكابتن الأنسب وتوقع النقاط\n"
                "• 🤕 متابعة تقارير الإصابات والشكوك الرسمية\n"
                "• 🔥 أفضل اللاعبين المتوقع تألقهم\n"
                "• 💎 خيارات الـ Differentials ذات الملكية المنخفضة\n\n"
                "جرّب سؤالي مثل: **«تفتكر اكبتن مين الجولة الجاية؟»** أو **«مين المصابين؟»**"
            )
        else:
            resp = (
                f"I'm your Fantasy AI Assistant for Gameweek{gw_str}! ⚽\n\n"
                "I can analyze and recommend:\n"
                "• 🏆 Captain recommendations based on expected points\n"
                "• 🤕 Official injury status and rotation risks\n"
                "• 🔥 Top predicted players across all positions\n"
                "• 💎 Low-ownership differential picks\n\n"
                "Try asking: **'Who should I captain this gameweek?'** or **'Which players are injured?'**"
            )

        updated_history = list(conversation_history or [])
        updated_history.append({"role": "user", "content": user_message})
        updated_history.append({"role": "assistant", "content": resp})

        return {
            "response": resp,
            "tool_calls": [],
            "conversation": updated_history,
        }
