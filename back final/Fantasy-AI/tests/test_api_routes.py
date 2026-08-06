"""Route-level tests for the Fantasy-AI API, using FastAPI's TestClient.

These tests bypass the real ``lifespan`` startup (which reads files
from disk) by constructing the app fresh and injecting a fake
:class:`~src.api.state.AppState` directly into ``app.state`` — this
keeps the tests fast, hermetic, and independent of any trained model
or dataset being present on disk.

NOTE: this test module requires `fastapi`, `httpx`, and `pydantic`
to be installed (see requirements.txt) — it could not be executed in
the sandbox this project was built in (no internet access to install
those packages there). Please run `pytest -v` with them installed to
confirm this file before relying on it.
"""

from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.config.settings import get_settings
from src.prediction.loader import LoadedModel


class _StubModel:
    """A trivial stand-in for a fitted scikit-learn-compatible model."""

    def predict(self, X):  # noqa: N803 - sklearn convention
        return [7.5] * len(X)


@pytest.fixture
def client() -> TestClient:
    """Build a TestClient with a fake AppState injected (no disk I/O)."""
    app = create_app()

    engineered_data = pd.DataFrame(
        {
            "element": [1, 2, 3, 4],
            "name": ["Salah", "Haaland", "Kane", "BenchWarmer"],
            "season": ["2022-23"] * 4,
            "GW": [10, 10, 10, 10],
            "minutes_avg_last_3": [88.0, 90.0, 85.0, 12.0],
            "total_points": [8, 11, 6, 2],
        }
    )

    predictions = engineered_data.copy()
    predictions["predicted_for_gw"] = 11
    predictions["predicted_total_points"] = [6.5, 9.2, 5.1, 8.0]

    loaded_model = LoadedModel(
        model=_StubModel(),
        model_name="stub_model",
        feature_columns=["minutes_avg_last_3"],
        target_column="total_points",
        train_medians={"minutes_avg_last_3": 80.0},
        metrics={"mae": 1.0, "rmse": 1.5, "r2": 0.8},
    )

    from src.api.state import AppState

    app.state.fantasy_ai_state = AppState(
        settings=get_settings(),
        engineered_data=engineered_data,
        loaded_model=loaded_model,
        predictions=predictions,
        player_id_column="element",
    )

    return TestClient(app)


def test_health_reports_ok_when_state_loaded(client: TestClient) -> None:
    """GET / must report status 'ok' with model info once state is loaded."""
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["model_name"] == "stub_model"
    assert body["player_count"] == 4


def test_get_player_returns_latest_row(client: TestClient) -> None:
    """GET /player/{id} must return the player's latest known row."""
    response = client.get("/player/2")
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Haaland"


def test_get_player_404_for_unknown_id(client: TestClient) -> None:
    """GET /player/{id} must 404 for an unknown player."""
    response = client.get("/player/999")
    assert response.status_code == 404


def test_predict_returns_all_players_by_default(client: TestClient) -> None:
    """GET /predict with no query param must return every player's prediction."""
    response = client.get("/predict")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 4
    assert body["predictions"][0]["name"] == "Haaland"  # highest predicted


def test_predict_filters_by_player_id(client: TestClient) -> None:
    """GET /predict?player_id=X must return only that player's prediction."""
    response = client.get("/predict", params={"player_id": "3"})
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["predictions"][0]["name"] == "Kane"


def test_predict_404_for_unknown_player_id(client: TestClient) -> None:
    """GET /predict?player_id=X must 404 for an unknown player."""
    response = client.get("/predict", params={"player_id": "999"})
    assert response.status_code == 404


def test_top_players_respects_limit(client: TestClient) -> None:
    """GET /top_players?limit=2 must return exactly 2 players, highest first."""
    response = client.get("/top_players", params={"limit": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert [p["name"] for p in body["predictions"]] == ["Haaland", "BenchWarmer"]


def test_captain_excludes_low_minutes_player(client: TestClient) -> None:
    """GET /captain must not recommend a low-minutes player even if predicted higher."""
    response = client.get("/captain")
    assert response.status_code == 200
    body = response.json()
    # BenchWarmer (8.0) outscores Salah/Kane but has low minutes; Haaland (9.2) wins clean.
    assert body["recommendation"]["name"] == "Haaland"
    assert body["pool_size"] == 3


def test_swagger_docs_available(client: TestClient) -> None:
    """The Swagger UI must be served at /swagger."""
    response = client.get("/swagger")
    assert response.status_code == 200


def test_openapi_schema_available(client: TestClient) -> None:
    """The raw OpenAPI schema must always be available."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"]


def test_routes_503_when_state_not_loaded() -> None:
    """Data-dependent routes must return 503 if startup state failed to load."""
    app = create_app()
    app.state.fantasy_ai_state = None
    client = TestClient(app)

    response = client.get("/top_players")
    assert response.status_code == 503

    # Health and docs must still work even without loaded state.
    assert client.get("/").status_code == 200
    assert client.get("/swagger").status_code == 200
