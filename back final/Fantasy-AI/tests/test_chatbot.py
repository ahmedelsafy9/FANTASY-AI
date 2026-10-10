"""Unit tests for the Chatbot tools, PlayerResolver, and ChatbotService."""

from datetime import datetime, timezone
import pandas as pd
import pytest

from src.chatbot.player_resolver import PlayerResolver
from src.chatbot.tools import ChatbotTools, TOOL_DEFINITIONS
from src.chatbot.service import ChatbotService
from src.api.state import AppState
from src.config.settings import Settings


@pytest.fixture
def sample_predictions() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "element": 1,
            "id": 1,
            "web_name": "Salah",
            "first_name": "Mohamed",
            "second_name": "Salah",
            "name": "Mohamed Salah",
            "team": "Liverpool",
            "position": "MID",
            "now_cost": 128,
            "predicted_expected_points": 8.4,
            "predicted_expected_points_raw": 8.4,
            "availability_status": "fit",
            "availability_expected_minutes": 90.0,
            "injury_flag": False,
            "doubt_flag": False,
            "suspension_flag": False,
            "ruled_out_flag": False,
            "team_news": "",
            "chance_of_playing_next_round": 100,
            "selected_by_percent": 45.2,
            "fpl_form": 7.8,
            "captaincy_score": 16.8,
            "differential_flag": False,
        },
        {
            "element": 2,
            "id": 2,
            "web_name": "Palmer",
            "first_name": "Cole",
            "second_name": "Palmer",
            "name": "Cole Palmer",
            "team": "Chelsea",
            "position": "MID",
            "now_cost": 108,
            "predicted_expected_points": 7.6,
            "predicted_expected_points_raw": 7.6,
            "availability_status": "fit",
            "availability_expected_minutes": 90.0,
            "injury_flag": False,
            "doubt_flag": False,
            "suspension_flag": False,
            "ruled_out_flag": False,
            "team_news": "",
            "chance_of_playing_next_round": 100,
            "selected_by_percent": 38.0,
            "fpl_form": 8.1,
            "captaincy_score": 15.2,
            "differential_flag": False,
        },
        {
            "element": 3,
            "id": 3,
            "web_name": "De Bruyne",
            "first_name": "Kevin",
            "second_name": "De Bruyne",
            "name": "Kevin De Bruyne",
            "team": "Man City",
            "position": "MID",
            "now_cost": 95,
            "predicted_expected_points": 2.5,
            "predicted_expected_points_raw": 5.0,
            "availability_status": "doubtful",
            "availability_expected_minutes": 45.0,
            "injury_flag": False,
            "doubt_flag": True,
            "suspension_flag": False,
            "ruled_out_flag": False,
            "team_news": "Hamstring strain - 50% chance of playing",
            "chance_of_playing_next_round": 50,
            "selected_by_percent": 8.0,
            "fpl_form": 4.0,
            "captaincy_score": 5.0,
            "differential_flag": True,
        },
        {
            "element": 4,
            "id": 4,
            "web_name": "Saliba",
            "first_name": "William",
            "second_name": "Saliba",
            "name": "William Saliba",
            "team": "Arsenal",
            "position": "DEF",
            "now_cost": 60,
            "predicted_expected_points": 0.0,
            "predicted_expected_points_raw": 4.5,
            "availability_status": "major_injury",
            "availability_expected_minutes": 0.0,
            "injury_flag": True,
            "doubt_flag": False,
            "suspension_flag": False,
            "ruled_out_flag": True,
            "team_news": "Back injury - Unknown return date",
            "chance_of_playing_next_round": 0,
            "selected_by_percent": 25.0,
            "fpl_form": 3.0,
            "captaincy_score": 0.0,
            "differential_flag": False,
        },
    ])


from src.prediction.loader import LoadedModel


@pytest.fixture
def mock_app_state(sample_predictions: pd.DataFrame) -> AppState:
    settings = Settings()
    loaded_model = LoadedModel(
        model=None,
        model_name="mock",
        feature_columns=[],
        target_column="target",
        train_medians={},
        metrics={},
    )
    return AppState(
        settings=settings,
        engineered_data=pd.DataFrame(),
        loaded_model=loaded_model,
        predictions=sample_predictions,
        player_id_column="element",
        live_metadata_available=True,
        predicted_gameweek=5,
        latest_completed_gameweek=4,
        season="2026-27",
        generated_at=datetime.now(timezone.utc).isoformat(),
        scoring_model="multi_objective_v1",
        differential_predictions=sample_predictions[sample_predictions["differential_flag"] == True],
    )


def test_player_resolver_english(sample_predictions: pd.DataFrame):
    resolver = PlayerResolver(sample_predictions)
    
    # Exact web name
    res = resolver.resolve("Salah")
    assert len(res) >= 1
    assert res[0]["web_name"] == "Salah"

    # Full name
    res = resolver.resolve("Cole Palmer")
    assert len(res) >= 1
    assert res[0]["web_name"] == "Palmer"

    # Abbreviation
    res = resolver.resolve("KDB")
    assert len(res) >= 1
    assert res[0]["web_name"] == "De Bruyne"


def test_player_resolver_arabic(sample_predictions: pd.DataFrame):
    resolver = PlayerResolver(sample_predictions)

    # Arabic transliteration for Salah
    res = resolver.resolve("صلاح")
    assert len(res) >= 1
    assert res[0]["web_name"] == "Salah"

    # Arabic for Palmer
    res = resolver.resolve("بالمر")
    assert len(res) >= 1
    assert res[0]["web_name"] == "Palmer"


def test_chatbot_tools(mock_app_state: AppState):
    tools = ChatbotTools(mock_app_state)

    # 1. search_player_by_name
    search_res = tools.search_player_by_name("Salah")
    assert isinstance(search_res, list)
    assert len(search_res) >= 1
    assert search_res[0]["web_name"] == "Salah"

    # 2. get_player_info
    info = tools.get_player_info(player_name="Palmer")
    assert info["web_name"] == "Palmer"
    assert info["team"] == "Chelsea"

    # 3. get_player_availability
    avail = tools.get_player_availability(player_name="Saliba")
    assert avail["availability_status"] == "major_injury"
    assert avail["ruled_out_flag"] is True

    # 4. compare_players
    comp = tools.compare_players("Salah", "Palmer")
    assert "player1" in comp
    assert "player2" in comp
    assert comp["player1"]["web_name"] == "Salah"
    assert comp["player2"]["web_name"] == "Palmer"

    # 5. get_captain_recommendation
    cap = tools.get_captain_recommendation()
    assert "candidates" in cap

    # 6. get_current_gameweek
    gw = tools.get_current_gameweek()
    assert gw["predicted_gameweek"] == 5

    # 7. get_injured_doubtful_players
    inj = tools.get_injured_doubtful_players()
    assert inj["count"] >= 2


def test_chatbot_service_fallback(mock_app_state: AppState):
    # Without API key, service should return graceful fallback response
    service = ChatbotService(mock_app_state, api_key="")
    assert service.is_configured is False

    res = service._fallback_response("Who should I captain?")
    assert "response" in res
    assert "captain" in res["response"].lower() or "candidate" in res["response"].lower()
    assert res.get("fallback") is True
    assert res.get("provider") == "fallback"

    res_inj = service._fallback_response("Are there injured players?")
    assert "response" in res_inj
    assert "players" in res_inj["response"].lower()
    assert res_inj.get("fallback") is True
    assert res_inj.get("provider") == "fallback"


def test_gemini_model_configuration_and_normalization(mock_app_state: AppState):
    from src.config.settings import ChatbotSettings

    # 1. Default model is gemini-3.8-flash
    svc = ChatbotService(mock_app_state, api_key="")
    assert svc._model == "gemini-3.8-flash"

    # 2. Strips 'models/' prefix
    svc_prefix = ChatbotService(mock_app_state, api_key="", model="models/gemini-3.8-flash")
    assert svc_prefix._model == "gemini-3.8-flash"

    # 3. Strips whitespace
    svc_ws = ChatbotService(mock_app_state, api_key="", model="  gemini-3.8-flash  ")
    assert svc_ws._model == "gemini-3.8-flash"

    # 4. Settings default and normalization
    cfg = ChatbotSettings()
    assert "models/" not in cfg.llm_model


def test_gemini_env_variable_overrides(monkeypatch):
    from src.config.settings import ChatbotSettings

    # FANTASY_AI_LLM_MODEL override
    monkeypatch.setenv("FANTASY_AI_LLM_MODEL", "models/custom-test-flash")
    cfg = ChatbotSettings()
    assert cfg.llm_model == "custom-test-flash"

    # Fallback to GEMINI_MODEL when FANTASY_AI_LLM_MODEL is not set
    monkeypatch.delenv("FANTASY_AI_LLM_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_MODEL", "models/gemini-3.8-pro")
    cfg2 = ChatbotSettings()
    assert cfg2.llm_model == "gemini-3.8-pro"


def test_gemini_error_classification():
    from src.chatbot.service import _classify_gemini_error

    # Model not found / deprecated
    e404 = Exception("404 NOT_FOUND: models/gemini-2.5-flash is no longer available to new users.")
    cat, summary, is_perm = _classify_gemini_error(e404)
    assert cat == "MODEL_NOT_FOUND"
    assert is_perm is True

    # Authentication failure
    e401 = Exception("401 UNAUTHENTICATED: API_KEY_INVALID")
    cat, summary, is_perm = _classify_gemini_error(e401)
    assert cat == "AUTH_ERROR"
    assert is_perm is True

    # Quota / Rate limit
    e429 = Exception("429 RESOURCE_EXHAUSTED: Quota exceeded for quota metric")
    cat, summary, is_perm = _classify_gemini_error(e429)
    assert cat == "QUOTA_EXHAUSTED"
    assert is_perm is False

    # Network / Timeout
    etimeout = TimeoutError("Connection timed out after 30s")
    cat, summary, is_perm = _classify_gemini_error(etimeout)
    assert cat == "NETWORK_ERROR"
    assert is_perm is False

    # Secrets sanitization test
    e_leak = Exception("Request failed for key=AIzaSyDfakeSecretKey1234567890123456789 in query")
    cat, summary, is_perm = _classify_gemini_error(e_leak)
    assert "AIzaSyDfake" not in summary
    assert "[REDACTED" in summary


def test_gemini_fallback_on_model_not_found(mock_app_state: AppState, monkeypatch):
    """Verify that a 404 model-not-found error immediately falls back without retrying."""
    import asyncio
    from unittest.mock import MagicMock

    call_count = 0

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.models = MagicMock()
            def mock_generate(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                raise Exception("404 NOT_FOUND: models/gemini-2.5-flash is no longer available.")
            self.models.generate_content.side_effect = mock_generate

    import google.genai as genai_module
    monkeypatch.setattr(genai_module, "Client", FakeClient)

    svc = ChatbotService(mock_app_state, api_key="fake-test-key", model="gemini-2.5-flash")
    result = asyncio.run(svc.chat("Who should I captain?"))

    # Ensure it did not repeatedly loop or retry
    assert call_count == 1
    assert result.get("fallback") is True
    assert result.get("provider") == "fallback"
    assert "gemini_model_not_found" in result.get("fallback_reason", "")
    assert len(result.get("response", "")) > 0


def test_gemini_successful_generation_mock(mock_app_state: AppState, monkeypatch):
    """Verify successful Gemini generation passes through without fallback."""
    import asyncio
    from unittest.mock import MagicMock

    class FakeCandidate:
        content = MagicMock(parts=[MagicMock(text="Captain Haaland for GW5.", function_call=None)])

    class FakeResponse:
        text = "Captain Haaland for GW5."
        candidates = [FakeCandidate()]

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.models = MagicMock()
            self.models.generate_content.return_value = FakeResponse()

    import google.genai as genai_module
    monkeypatch.setattr(genai_module, "Client", FakeClient)

    svc = ChatbotService(mock_app_state, api_key="fake-test-key", model="gemini-3.8-flash")
    result = asyncio.run(svc.chat("Who should I captain?"))

    assert result.get("fallback") is False
    assert result.get("provider") == "gemini"
    assert result.get("model") == "gemini-3.8-flash"
    assert result.get("response") == "Captain Haaland for GW5."


def test_gemini_tool_calling_execution_mock(mock_app_state: AppState, monkeypatch):
    """Verify Gemini function calling iteration: model requests tool, tool executes, result returns to model."""
    import asyncio
    from unittest.mock import MagicMock

    call_index = 0

    class FakeFC:
        name = "get_captain_recommendation"
        args = {}

    class FakePart1:
        text = None
        function_call = FakeFC()

    class FakeCandidate1:
        content = MagicMock(parts=[FakePart1()])

    class FakeResponse1:
        text = ""
        candidates = [FakeCandidate1()]

    class FakePart2:
        text = "Based on tool results, Haaland is top captain."
        function_call = None

    class FakeCandidate2:
        content = MagicMock(parts=[FakePart2()])

    class FakeResponse2:
        text = "Based on tool results, Haaland is top captain."
        candidates = [FakeCandidate2()]

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.models = MagicMock()
            def mock_generate(*args, **kwargs):
                nonlocal call_index
                call_index += 1
                if call_index == 1:
                    return FakeResponse1()
                return FakeResponse2()
            self.models.generate_content.side_effect = mock_generate

    import google.genai as genai_module
    monkeypatch.setattr(genai_module, "Client", FakeClient)

    svc = ChatbotService(mock_app_state, api_key="fake-test-key", model="gemini-3.8-flash")
    result = asyncio.run(svc.chat("Who should I captain?"))

    assert call_index == 2
    assert result.get("fallback") is False
    assert result.get("provider") == "gemini"
    assert len(result.get("tool_calls", [])) == 1
    assert result["tool_calls"][0]["tool"] == "get_captain_recommendation"
    assert "Haaland is top captain" in result["response"]


