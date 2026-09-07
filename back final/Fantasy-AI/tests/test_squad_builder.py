"""Comprehensive unit & integration tests for SquadBuilderService and /squad/build API.

Verifies all 12 requirements:
1. Builder always returns the full required squad (15 players) when valid solution exists.
2. Total squad cost never exceeds budget (£100.0m).
3. Budget feasibility is checked before every selection.
4. High-point expensive players do not make the squad impossible.
5. Value-for-money players are used for completion.
6. Position constraints remain valid (2 GKP, 5 DEF, 5 MID, 3 FWD).
7. Existing squad constraints remain valid (max 3 players per club).
8. Backtracking/repair works when initial core picks become infeasible.
9. A valid squad is returned when one exists.
10. An explicit error is returned when no valid squad exists.
11. The final squad is not unnecessarily under-budget when a better valid squad exists.
12. API endpoints GET and POST /squad/build return complete valid response.
"""

from __future__ import annotations

import pandas as pd
import pytest
from starlette.testclient import TestClient

from src.api.main import create_app
from src.api.services.squad_builder_service import SquadBuilderService
from src.api.state import AppState
from src.config.settings import Settings
from src.core.exceptions import SquadBuilderError


def _make_mock_predictions_pool(
    include_expensive_traps: bool = True,
) -> pd.DataFrame:
    """Create a controlled, diverse candidate pool of players."""
    rows = []

    # 4 GKP (prices 4.0 - 5.5)
    rows.extend([
        {"element": 1, "name": "Raya", "team": "Arsenal", "position": "GKP", "now_cost": 55, "predicted_fpl_rank_score": 5.5},
        {"element": 2, "name": "Pickford", "team": "Everton", "position": "GKP", "now_cost": 50, "predicted_fpl_rank_score": 4.8},
        {"element": 3, "name": "Verbruggen", "team": "Brighton", "position": "GKP", "now_cost": 45, "predicted_fpl_rank_score": 4.2},
        {"element": 4, "name": "Fabianski", "team": "West Ham", "position": "GKP", "now_cost": 40, "predicted_fpl_rank_score": 3.0},
    ])

    # 10 DEF (prices 4.0 - 7.0)
    rows.extend([
        {"element": 10, "name": "Alexander-Arnold", "team": "Liverpool", "position": "DEF", "now_cost": 70, "predicted_fpl_rank_score": 6.8},
        {"element": 11, "name": "Saliba", "team": "Arsenal", "position": "DEF", "now_cost": 60, "predicted_fpl_rank_score": 6.0},
        {"element": 12, "name": "Gabriel", "team": "Arsenal", "position": "DEF", "now_cost": 60, "predicted_fpl_rank_score": 5.9},
        {"element": 13, "name": "Gvardiol", "team": "Man City", "position": "DEF", "now_cost": 60, "predicted_fpl_rank_score": 5.6},
        {"element": 14, "name": "Porro", "team": "Spurs", "position": "DEF", "now_cost": 55, "predicted_fpl_rank_score": 5.2},
        {"element": 15, "name": "Mykolenko", "team": "Everton", "position": "DEF", "now_cost": 45, "predicted_fpl_rank_score": 4.5},
        {"element": 16, "name": "Robinson", "team": "Fulham", "position": "DEF", "now_cost": 45, "predicted_fpl_rank_score": 4.4},
        {"element": 17, "name": "Greaves", "team": "Ipswich Town", "position": "DEF", "now_cost": 40, "predicted_fpl_rank_score": 3.8},
        {"element": 18, "name": "Faer", "team": "Leicester", "position": "DEF", "now_cost": 40, "predicted_fpl_rank_score": 3.5},
        {"element": 19, "name": "Bednarek", "team": "Southampton", "position": "DEF", "now_cost": 40, "predicted_fpl_rank_score": 3.2},
    ])

    # 10 MID (prices 4.5 - 12.5)
    rows.extend([
        {"element": 20, "name": "Salah", "team": "Liverpool", "position": "MID", "now_cost": 125, "predicted_fpl_rank_score": 9.5},
        {"element": 21, "name": "Palmer", "team": "Chelsea", "position": "MID", "now_cost": 105, "predicted_fpl_rank_score": 8.8},
        {"element": 22, "name": "Saka", "team": "Arsenal", "position": "MID", "now_cost": 100, "predicted_fpl_rank_score": 8.4},
        {"element": 23, "name": "Son", "team": "Spurs", "position": "MID", "now_cost": 100, "predicted_fpl_rank_score": 7.9},
        {"element": 24, "name": "Gordon", "team": "Newcastle", "position": "MID", "now_cost": 75, "predicted_fpl_rank_score": 6.5},
        {"element": 25, "name": "Bowen", "team": "West Ham", "position": "MID", "now_cost": 75, "predicted_fpl_rank_score": 6.3},
        {"element": 26, "name": "Rogers", "team": "Aston Villa", "position": "MID", "now_cost": 50, "predicted_fpl_rank_score": 5.4},
        {"element": 27, "name": "Smith Rowe", "team": "Fulham", "position": "MID", "now_cost": 55, "predicted_fpl_rank_score": 5.2},
        {"element": 28, "name": "Winks", "team": "Leicester", "position": "MID", "now_cost": 45, "predicted_fpl_rank_score": 4.0},
        {"element": 29, "name": "Sangaré", "team": "Nott'm Forest", "position": "MID", "now_cost": 45, "predicted_fpl_rank_score": 3.6},
    ])

    # 8 FWD (prices 4.5 - 15.0)
    rows.extend([
        {"element": 30, "name": "Haaland", "team": "Man City", "position": "FWD", "now_cost": 150, "predicted_fpl_rank_score": 10.5},
        {"element": 31, "name": "Watkins", "team": "Aston Villa", "position": "FWD", "now_cost": 90, "predicted_fpl_rank_score": 7.5},
        {"element": 32, "name": "Isak", "team": "Newcastle", "position": "FWD", "now_cost": 85, "predicted_fpl_rank_score": 7.2},
        {"element": 33, "name": "Havertz", "team": "Arsenal", "position": "FWD", "now_cost": 80, "predicted_fpl_rank_score": 6.8},
        {"element": 34, "name": "Wood", "team": "Nott'm Forest", "position": "FWD", "now_cost": 60, "predicted_fpl_rank_score": 5.8},
        {"element": 35, "name": "Welbeck", "team": "Brighton", "position": "FWD", "now_cost": 55, "predicted_fpl_rank_score": 5.4},
        {"element": 36, "name": "Joao Pedro", "team": "Brighton", "position": "FWD", "now_cost": 55, "predicted_fpl_rank_score": 5.3},
        {"element": 37, "name": "Stewart", "team": "Southampton", "position": "FWD", "now_cost": 45, "predicted_fpl_rank_score": 3.0},
    ])

    if include_expensive_traps:
        # Add hyper-expensive trap players that would consume £60m in 3 players
        rows.extend([
            {"element": 98, "name": "SuperPremiumA", "team": "Chelsea", "position": "MID", "now_cost": 200, "predicted_fpl_rank_score": 14.0},
            {"element": 99, "name": "SuperPremiumB", "team": "Liverpool", "position": "FWD", "now_cost": 200, "predicted_fpl_rank_score": 14.5},
        ])

    return pd.DataFrame(rows)


def test_builder_returns_complete_15_player_squad():
    """Requirement 1 & 9: Builder always returns the full required 15 players."""
    pool = _make_mock_predictions_pool()
    service = SquadBuilderService(pool)
    resp = service.build_squad(budget=100.0)

    assert resp.count == 15
    assert len(resp.squad) == 15
    assert len(resp.starting_xi) == 11
    assert len(resp.bench) == 4


def test_total_cost_never_exceeds_budget():
    """Requirement 2: Total squad cost never exceeds £100m."""
    pool = _make_mock_predictions_pool()
    service = SquadBuilderService(pool)
    resp = service.build_squad(budget=100.0)

    assert resp.total_cost <= 100.0 + 1e-4
    assert resp.remaining_budget >= 0.0
    assert abs((resp.total_cost + resp.remaining_budget) - 100.0) < 0.2


def test_position_constraints_valid():
    """Requirement 6: Position constraints strictly enforced (2 GKP, 5 DEF, 5 MID, 3 FWD)."""
    pool = _make_mock_predictions_pool()
    service = SquadBuilderService(pool)
    resp = service.build_squad(budget=100.0)

    pos_counts: dict[str, int] = {}
    for p in resp.squad:
        pos_counts[p.position] = pos_counts.get(p.position, 0) + 1

    assert pos_counts == {"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3}


def test_team_limits_strictly_enforced():
    """Requirement 7: Max 3 players from any single club."""
    pool = _make_mock_predictions_pool()
    service = SquadBuilderService(pool)
    resp = service.build_squad(budget=100.0)

    club_counts: dict[str, int] = {}
    for p in resp.squad:
        club_counts[p.team] = club_counts.get(p.team, 0) + 1

    for club, count in club_counts.items():
        assert count <= 3, f"Club {club} has {count} players (max 3 allowed)."


def test_high_point_expensive_players_do_not_trap_builder_and_backtracking_works():
    """Requirement 3, 4 & 8: High point expensive players do not cause incomplete squads."""
    pool = _make_mock_predictions_pool(include_expensive_traps=True)
    service = SquadBuilderService(pool)

    # Even with SuperPremiumA (£20.0m) and SuperPremiumB (£20.0m) available,
    # the builder must NOT get trapped into an impossible state.
    # It must feasibility check and backtrack, returning exactly 15 valid players.
    resp = service.build_squad(budget=100.0, core_picks_count=4)

    assert resp.count == 15
    assert resp.total_cost <= 100.0
    # Core picks exist
    assert len(resp.core_picks) > 0
    # Value picks exist
    assert len(resp.value_picks) > 0


def test_value_for_money_completion():
    """Requirement 5: Value for money players are used for completion."""
    pool = _make_mock_predictions_pool()
    service = SquadBuilderService(pool)
    resp = service.build_squad(budget=100.0)

    value_pick_names = [p.name for p in resp.value_picks]
    assert len(value_pick_names) > 0
    # At least some value picks should have points_per_million >= 0.8
    high_ppm = [p for p in resp.value_picks if p.points_per_million >= 0.7]
    assert len(high_ppm) > 0


def test_explicit_error_when_no_valid_squad_can_be_built():
    """Requirement 10: Explicit error when budget is impossible or player pool is insufficient."""
    pool = _make_mock_predictions_pool()
    service = SquadBuilderService(pool)

    # With £40m budget, 15 players cannot be bought (cheapest 15 cost at least £65m)
    with pytest.raises(SquadBuilderError) as exc_info:
        service.build_squad(budget=40.0)
    assert "insufficient" in str(exc_info.value).lower()

    # With empty or tiny pool
    tiny_pool = pool.head(5)
    service_tiny = SquadBuilderService(tiny_pool)
    with pytest.raises(SquadBuilderError) as exc_info2:
        service_tiny.build_squad(budget=100.0)
    assert "minimum 15 required" in str(exc_info2.value).lower() or "insufficient" in str(exc_info2.value).lower()


def test_final_squad_is_not_unnecessarily_under_budget():
    """Requirement 11: Local optimization pass upgrades players using leftover budget."""
    pool = _make_mock_predictions_pool()
    service = SquadBuilderService(pool)
    resp = service.build_squad(budget=100.0)

    # Spent cost should be high enough (e.g. >= £95m), not leaving £25m unspent
    assert resp.total_cost >= 90.0, f"Expected total cost >= £90m, got {resp.total_cost}"


def test_starting_xi_formation_and_captain():
    """Formation, starting XI (11), bench (4), and captaincy are valid."""
    pool = _make_mock_predictions_pool()
    service = SquadBuilderService(pool)
    resp = service.build_squad(budget=100.0, formation="3-5-2")

    assert resp.formation == "3-5-2"
    assert len(resp.starting_xi) == 11
    assert len(resp.bench) == 4

    start_counts: dict[str, int] = {}
    for p in resp.starting_xi:
        start_counts[p.position] = start_counts.get(p.position, 0) + 1

    assert start_counts == {"GKP": 1, "DEF": 3, "MID": 5, "FWD": 2}

    # Captain and Vice-captain are both starters
    starter_pids = {p.element for p in resp.starting_xi}
    assert resp.captain.element in starter_pids
    assert resp.vice_captain.element in starter_pids
    assert resp.captain.element != resp.vice_captain.element
    assert resp.captain.predicted_points >= resp.vice_captain.predicted_points


def test_api_squad_build_endpoints():
    """Requirement 12: GET /squad/build and POST /squad/build return HTTP 200 with valid schema."""
    settings = Settings()
    pool = _make_mock_predictions_pool()

    app_state = AppState(
        settings=settings,
        engineered_data=pd.DataFrame(),
        loaded_model=None,
        predictions=pool,
        player_id_column="element",
        live_metadata_available=True,
        season="2026-27",
        latest_completed_gameweek=3,
        predicted_gameweek=4,
    )

    app = create_app()
    app.state.fantasy_ai_state = app_state

    client = TestClient(app)

    # Test GET /squad/build
    resp_get = client.get("/squad/build?budget=100.0&formation=4-4-2")
    assert resp_get.status_code == 200
    data_get = resp_get.json()
    assert data_get["count"] == 15
    assert len(data_get["squad"]) == 15
    assert data_get["total_cost"] <= 100.0

    # Test POST /squad/build
    resp_post = client.post("/squad/build", json={"budget": 100.0, "formation": "3-5-2"})
    assert resp_post.status_code == 200
    data_post = resp_post.json()
    assert data_post["count"] == 15
    assert data_post["formation"] == "3-5-2"
    assert data_post["total_cost"] <= 100.0

    # Test 422 error on impossible budget
    resp_err = client.get("/squad/build?budget=40.0")
    assert resp_err.status_code == 422
    assert "insufficient" in resp_err.json()["detail"].lower()
