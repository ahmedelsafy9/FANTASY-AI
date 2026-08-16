"""Security-hardening tests for the Fantasy-AI API.

Covers the fixes added in the pre-launch security audit: CORS lockdown
(no unintended origins, no unintended credentials), security headers,
safe (non-leaky) error responses, per-IP rate limiting, and bounded
query/path input.

Reuses the same fake-AppState pattern as ``test_api_routes.py`` so
these tests stay hermetic (no disk I/O, no real model).
"""

from __future__ import annotations

import os

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.state import AppState
from src.config.settings import get_settings
from src.prediction.loader import LoadedModel


class _StubModel:
    def predict(self, X):  # noqa: N803 - sklearn convention
        return [7.5] * len(X)


def _build_client(model=None, *, raise_server_exceptions: bool = True) -> TestClient:
    app = create_app()

    engineered_data = pd.DataFrame(
        {
            "element": [1, 2, 3],
            "name": ["Salah", "Haaland", "Kane"],
            "season": ["2022-23"] * 3,
            "GW": [10, 10, 10],
            "minutes_avg_last_3": [88.0, 90.0, 85.0],
            "total_points": [8, 11, 6],
        }
    )
    predictions = engineered_data.copy()
    predictions["predicted_for_gw"] = 11
    predictions["predicted_total_points"] = [6.5, 9.2, 5.1]

    loaded_model = LoadedModel(
        model=model or _StubModel(),
        model_name="stub_model",
        feature_columns=["minutes_avg_last_3"],
        target_column="total_points",
        train_medians={"minutes_avg_last_3": 80.0},
        metrics={"mae": 1.0, "rmse": 1.5, "r2": 0.8},
    )

    app.state.fantasy_ai_state = AppState(
        settings=get_settings(),
        engineered_data=engineered_data,
        loaded_model=loaded_model,
        predictions=predictions,
        player_id_column="element",
    )
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


@pytest.fixture
def client() -> TestClient:
    return _build_client()


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------


def test_cors_allows_all_default_dev_origins(client: TestClient) -> None:
    """All 4 standard local dev origins must get CORS headers back in development."""
    dev_origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
    for origin in dev_origins:
        response = client.get("/", headers={"Origin": origin})
        assert response.headers.get("access-control-allow-origin") == origin


def test_cors_rejects_unknown_origin(client: TestClient) -> None:
    """An arbitrary, unrecognized origin must NOT get an ACAO header back."""
    response = client.get("/", headers={"Origin": "https://evil.example.com"})
    assert "access-control-allow-origin" not in {k.lower() for k in response.headers}


def test_cors_options_preflight_request(client: TestClient) -> None:
    """Preflight OPTIONS request from an allowed origin must return 200 and CORS headers."""
    response = client.options(
        "/top_players",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Content-Type,Authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    allowed_methods = response.headers.get("access-control-allow-methods", "")
    assert "GET" in allowed_methods
    assert "OPTIONS" in allowed_methods


def test_cors_options_preflight_rejects_unknown_origin(client: TestClient) -> None:
    """Preflight OPTIONS request from an unknown origin must not return ACAO header."""
    response = client.options(
        "/top_players",
        headers={
            "Origin": "https://untrusted.site",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in {k.lower() for k in response.headers}


def test_cors_production_multiple_origins_and_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    """In production, multiple comma-separated origins with whitespace/empty items are parsed cleanly."""
    monkeypatch.setenv("FANTASY_AI_ENV", "production")
    monkeypatch.setenv(
        "FANTASY_AI_CORS_ORIGINS",
        "  https://frontend-alpha.vercel.app  , ,  https://app.fantasyai.com , ",
    )
    client = _build_client()

    # Localhost should NOT be allowed in production
    res_local = client.get("/", headers={"Origin": "http://localhost:5173"})
    assert "access-control-allow-origin" not in {k.lower() for k in res_local.headers}

    # Configured origins must be allowed
    res_1 = client.get("/", headers={"Origin": "https://frontend-alpha.vercel.app"})
    assert res_1.headers.get("access-control-allow-origin") == "https://frontend-alpha.vercel.app"

    res_2 = client.get("/", headers={"Origin": "https://app.fantasyai.com"})
    assert res_2.headers.get("access-control-allow-origin") == "https://app.fantasyai.com"

    # Unlisted origin rejected
    res_unlisted = client.get("/", headers={"Origin": "https://other.com"})
    assert "access-control-allow-origin" not in {k.lower() for k in res_unlisted.headers}


def test_cors_roosters_frontend_origin_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The deployed production domain https://fantasy-ai-roosters.vercel.app must be allowed."""
    monkeypatch.setenv("FANTASY_AI_ENV", "production")
    monkeypatch.delenv("FANTASY_AI_CORS_ORIGINS", raising=False)
    client = _build_client()

    response = client.get("/", headers={"Origin": "https://fantasy-ai-roosters.vercel.app"})
    assert response.headers.get("access-control-allow-origin") == "https://fantasy-ai-roosters.vercel.app"


def test_cors_vercel_preview_origin_allowed_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """Vercel preview deployment URLs (https://*.vercel.app) must be allowed via regex in production."""
    monkeypatch.setenv("FANTASY_AI_ENV", "production")
    client = _build_client()

    preview_origin = "https://fantasy-ai-9qkn-pr2gagmsn-ahmedelsafy9s-projects.vercel.app"
    response = client.get("/top_players", headers={"Origin": preview_origin})
    assert response.headers.get("access-control-allow-origin") == preview_origin

    another_preview = "https://branch-preview-42.vercel.app"
    response2 = client.get("/", headers={"Origin": another_preview})
    assert response2.headers.get("access-control-allow-origin") == another_preview


def test_cors_vercel_preview_options_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    """Preflight OPTIONS request from a Vercel preview origin must succeed with CORS headers."""
    monkeypatch.setenv("FANTASY_AI_ENV", "production")
    client = _build_client()

    preview_origin = "https://fantasy-ai-9qkn-pr2gagmsn-ahmedelsafy9s-projects.vercel.app"
    response = client.options(
        "/top_players?limit=3",
        headers={
            "Origin": preview_origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Content-Type,Authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == preview_origin
    allowed_methods = response.headers.get("access-control-allow-methods", "")
    assert "GET" in allowed_methods
    assert "OPTIONS" in allowed_methods


def test_cors_rejects_malicious_domains_spoofing_vercel(monkeypatch: pytest.MonkeyPatch) -> None:
    """Domains that try to mimic vercel.app must be strictly rejected."""
    monkeypatch.setenv("FANTASY_AI_ENV", "production")
    client = _build_client()

    spoofed_origins = [
        "https://evil-vercel.app",
        "https://vercel.app.attacker.com",
        "http://insecure-preview.vercel.app",  # HTTP instead of HTTPS
        "https://fakevercel.app",
        "https://evil.com",
    ]
    for origin in spoofed_origins:
        response = client.get("/", headers={"Origin": origin})
        assert "access-control-allow-origin" not in {k.lower() for k in response.headers}


def test_cors_does_not_allow_credentials_by_default(client: TestClient) -> None:
    """Without FANTASY_AI_CORS_ALLOW_CREDENTIALS=true, no ACAC header is sent."""
    response = client.get("/", headers={"Origin": "http://localhost:5173"})
    assert "access-control-allow-credentials" not in {k.lower() for k in response.headers}


def test_cors_allows_credentials_when_explicitly_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """When FANTASY_AI_CORS_ALLOW_CREDENTIALS=true, ACAC header is sent."""
    monkeypatch.setenv("FANTASY_AI_CORS_ALLOW_CREDENTIALS", "true")
    client = _build_client()
    response = client.get("/", headers={"Origin": "http://localhost:5173"})
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_env_tuple_parser_handles_whitespace_and_empty() -> None:
    """_env_tuple should strip whitespace and ignore empty elements."""
    from src.config.settings import _env_tuple
    import os

    os.environ["_TEST_TUPLE"] = " http://a.com, , http://b.com ,   ,http://c.com "
    result = _env_tuple("_TEST_TUPLE")
    assert result == ("http://a.com", "http://b.com", "http://c.com")


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------


def test_security_headers_present(client: TestClient) -> None:
    response = client.get("/")
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("referrer-policy") == "no-referrer"


# ---------------------------------------------------------------------------
# Safe error responses
# ---------------------------------------------------------------------------


def test_unhandled_exception_returns_generic_500_without_internals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unexpected exception must not leak its message/traceback to the client."""
    import src.api.routers.predictions as predictions_module

    def _boom(*args, **kwargs):
        raise RuntimeError("/etc/passwd this-should-never-reach-the-client")

    monkeypatch.setattr(predictions_module, "_iter_rows", _boom)

    client = _build_client(raise_server_exceptions=False)
    response = client.get("/predict")
    assert response.status_code == 500
    body = response.json()
    assert body == {"detail": "Internal server error."}
    assert "passwd" not in response.text
    assert "RuntimeError" not in response.text
    assert "Traceback" not in response.text


def test_404_error_detail_does_not_leak_filesystem_info(client: TestClient) -> None:
    response = client.get("/player/does-not-exist")
    assert response.status_code == 404
    detail = response.json()["detail"]
    assert "/" not in detail.replace("does-not-exist", "")  # no path fragments leaked


# ---------------------------------------------------------------------------
# Input bounds
# ---------------------------------------------------------------------------


def test_top_players_limit_is_capped(client: TestClient) -> None:
    """A requested limit above the configured max must be capped, not honored."""
    response = client.get("/top_players", params={"limit": 500})  # > top_players_max_limit (100)
    assert response.status_code == 200
    assert response.json()["count"] <= 3  # only 3 players exist in the fixture


def test_top_players_rejects_absurd_limit_value(client: TestClient) -> None:
    response = client.get("/top_players", params={"limit": 10**18})
    assert response.status_code == 422


def test_player_id_rejects_overlong_value(client: TestClient) -> None:
    response = client.get("/player/" + "a" * 500)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


def test_rate_limit_returns_429_once_exceeded(monkeypatch: pytest.MonkeyPatch) -> None:
    """Requests beyond the configured per-IP limit must be rejected with 429."""
    monkeypatch.setenv("FANTASY_AI_RATE_LIMIT_DEFAULT", "3/minute")
    client = _build_client()

    statuses = [client.get("/").status_code for _ in range(5)]
    assert statuses[:3] == [200, 200, 200]
    assert 429 in statuses[3:]


def test_rate_limit_uses_fly_client_ip_header_not_forwarded_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rate limiting must key on Fly-Client-IP, not spoofable X-Forwarded-For.

    Two "clients" sharing the same TCP peer (as they would behind Fly's
    proxy) but presenting different Fly-Client-IP header values must be
    limited independently; an attacker-supplied X-Forwarded-For must
    have no effect at all.
    """
    monkeypatch.setenv("FANTASY_AI_RATE_LIMIT_DEFAULT", "2/minute")
    client = _build_client()

    # Client A exhausts its limit.
    for _ in range(2):
        assert client.get("/", headers={"Fly-Client-IP": "1.2.3.4"}).status_code == 200
    assert client.get("/", headers={"Fly-Client-IP": "1.2.3.4"}).status_code == 429

    # Client B, same test-transport peer, different Fly-Client-IP, is unaffected.
    assert client.get("/", headers={"Fly-Client-IP": "5.6.7.8"}).status_code == 200

    # Spoofing X-Forwarded-For alone (no Fly-Client-IP) must not grant a fresh quota.
    monkeypatch.setenv("FANTASY_AI_RATE_LIMIT_DEFAULT", "2/minute")
    client2 = _build_client()
    for _ in range(2):
        client2.get("/", headers={"X-Forwarded-For": "9.9.9.9"})
    spoofed = client2.get("/", headers={"X-Forwarded-For": "1.1.1.1"})
    assert spoofed.status_code == 429
