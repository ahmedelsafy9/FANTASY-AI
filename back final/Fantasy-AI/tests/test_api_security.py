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


def test_cors_allows_known_dev_origin(client: TestClient) -> None:
    """A recognized local dev origin gets CORS headers back (dev default)."""
    response = client.get("/", headers={"Origin": "http://localhost:5173"})
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_rejects_unknown_origin(client: TestClient) -> None:
    """An arbitrary, unrecognized origin must NOT get an ACAO header back."""
    response = client.get("/", headers={"Origin": "https://evil.example.com"})
    assert "access-control-allow-origin" not in {k.lower() for k in response.headers}


def test_cors_does_not_allow_credentials_by_default(client: TestClient) -> None:
    """Without FANTASY_AI_CORS_ALLOW_CREDENTIALS=true, no ACAC header is sent."""
    response = client.get("/", headers={"Origin": "http://localhost:5173"})
    assert "access-control-allow-credentials" not in {k.lower() for k in response.headers}


def test_cors_production_env_does_not_allow_localhost(monkeypatch: pytest.MonkeyPatch) -> None:
    """In production, localhost dev origins must not be trusted."""
    monkeypatch.setenv("FANTASY_AI_ENV", "production")
    monkeypatch.setenv("FANTASY_AI_CORS_ORIGINS", "https://myapp.example.com")
    client = _build_client()
    response = client.get("/", headers={"Origin": "http://localhost:5173"})
    assert "access-control-allow-origin" not in {k.lower() for k in response.headers}

    response = client.get("/", headers={"Origin": "https://myapp.example.com"})
    assert response.headers.get("access-control-allow-origin") == "https://myapp.example.com"


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
