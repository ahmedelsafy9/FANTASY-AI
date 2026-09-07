/**
 * Types mirroring the real Fantasy-AI backend (see the backend's
 * `src/api/schemas.py`). The backend deliberately returns loosely-typed
 * records (`dict[str, Any]`) because the underlying dataset's columns can
 * vary by season/source — so `PlayerRecord` below is a "best-known-fields"
 * shape with everything optional, plus an index signature for anything
 * else that might be present. NOTHING here is invented: every named field
 * corresponds to a real column the backend can produce. Consumers must
 * treat every field as possibly absent and render "N/A" or hide
 * gracefully rather than assume presence.
 */

/** An upcoming fixture for a player's team. */
export interface UpcomingFixture {
  fixture_id?: number | null;
  code?: number | null;
  event?: number | null;
  is_home: boolean;
  opponent_team_id: number;
  opponent_name: string;
  opponent_short_name?: string | null;
  opponent_logo_url?: string | null;
  difficulty?: number | null;
  kickoff_time?: string | null;
}

/** A single player/prediction record as returned by the backend. */
export interface PlayerRecord {
  element?: number;
  name?: string;
  name_normalized?: string;
  team?: string;
  opponent_team?: string;
  season?: string;
  GW?: number;
  predicted_for_gw?: number;
  value?: number;
  total_points?: number;
  minutes?: number;
  goals_scored?: number;
  assists?: number;
  bonus?: number;
  bps?: number;
  ict_index?: number;
  was_home?: boolean;
  is_home?: number;
  rest_days?: number;
  team_strength?: number | null;
  opponent_strength?: number | null;
  price_trend_last_1?: number;
  price_trend_last_5?: number;
  form_index?: number | null;
  total_points_avg_last_3?: number | null;
  total_points_avg_last_5?: number | null;
  total_points_avg_last_10?: number | null;
  minutes_avg_last_3?: number | null;
  minutes_avg_last_5?: number | null;
  minutes_avg_last_10?: number | null;
  bps_avg_last_3?: number | null;
  bps_avg_last_5?: number | null;
  bps_avg_last_10?: number | null;
  ict_index_avg_last_3?: number | null;
  ict_index_avg_last_5?: number | null;
  ict_index_avg_last_10?: number | null;
  xG_avg_last_3?: number | null;
  xG_avg_last_5?: number | null;
  xG_avg_last_10?: number | null;
  xA_avg_last_3?: number | null;
  xA_avg_last_5?: number | null;
  xA_avg_last_10?: number | null;
  predicted_total_points?: number;
  predicted_expected_points?: number;
  predicted_fpl_rank_score?: number | null;
  prob_high_score_6?: number | null;
  prob_high_score_8?: number | null;
  prob_high_score_10?: number | null;
  prob_high_score_12?: number | null;
  ceiling_p75?: number | null;
  ceiling_p85?: number | null;
  ceiling_p90?: number | null;
  prediction_signals?: {
    recent_form?: { score?: number | null; rating?: string; detail?: string };
    expected_minutes?: { score?: number | null; rating?: string; minutes?: number | null; detail?: string };
    fixture_difficulty?: { score?: number | null; rating?: string; difficulty?: number | null; detail?: string };
    opportunity?: { score?: number | null; rating?: string; detail?: string };
    attacking_threat?: { score?: number | null; rating?: string; detail?: string };
    [key: string]: unknown;
  } | null;
  predicted_floor_points?: number;
  predicted_p50_points?: number;
  predicted_p75_points?: number;
  predicted_p85_points?: number;
  predicted_p90_points?: number;
  predicted_p95_points?: number;
  predicted_ceiling_points?: number;
  predicted_upside_points?: number;
  captaincy_score?: number;
  rank_expected?: number;
  rank_upside?: number;
  rank_captaincy?: number;
  predicted_goals?: number;
  predicted_assists?: number;
  predicted_clean_sheet_prob?: number;
  predicted_clean_sheet_probability?: number;
  predicted_p_play_any?: number;
  predicted_p_play_60?: number;
  predicted_minutes_probability?: number;
  predicted_minutes_60_probability?: number;
  predicted_expected_minutes?: number;
  predicted_goals_conceded?: number;
  predicted_saves?: number;
  predicted_yellow_cards?: number;
  predicted_red_cards?: number;
  predicted_bonus?: number;
  predicted_appearance_points?: number;
  predicted_goal_points?: number;
  predicted_assist_points?: number;
  predicted_clean_sheet_points?: number;
  predicted_goals_conceded_points?: number;
  predicted_save_points?: number;
  predicted_card_points?: number;
  predicted_bonus_points?: number;
  points_breakdown?: {
    appearance_points?: number;
    goal_points?: number;
    assist_points?: number;
    clean_sheet_points?: number;
    goals_conceded_points?: number;
    save_points?: number;
    card_points?: number;
    bonus_points?: number;
    total_points?: number;
  };
  position?: string;
  /** Phase 3: real upcoming-fixture data, where the live FPL API was reachable. */
  fixture_difficulty?: number | null;
  fixture_source?: "real_fixture" | "proxy_last_played";
  upcoming_fixtures?: UpcomingFixture[];
  /** Phase 4: statistically-grounded uncertainty (never a fabricated confidence %). */
  model_test_rmse?: number;
  prediction_uncertainty_std?: number;
  /** Phase 5: presentation metadata, built from real backend fields — null when unavailable. */
  photo_url?: string | null;
  team_logo_url?: string | null;
  opponent_logo_url?: string | null;
  /** Any other column the backend happens to expose for this row. */
  [key: string]: unknown;
}

/** GET /player/{player_id} */
export interface PlayerResponse {
  data: PlayerRecord;
}

/** GET /predict, GET /top_players */
export interface PredictionListResponse {
  count: number;
  season?: string | null;
  latest_completed_gameweek?: number | null;
  predicted_gameweek?: number | null;
  generated_at?: string | null;
  predicted_for_gw_note: string;
  predictions: PlayerRecord[];
}

/** GET /captain */
export interface CaptainResponse {
  recommendation: PlayerRecord;
  reasoning: string;
  pool_size: number;
}

/** GET / */
export interface HealthResponse {
  status: string;
  model_name?: string | null;
  player_count?: number | null;
  live_metadata_available?: boolean | null;
  season?: string | null;
  latest_completed_gameweek?: number | null;
  predicted_gameweek?: number | null;
}

/** Shape of a FastAPI HTTPException error body, e.g. { "detail": "..." } */
export interface ApiErrorBody {
  detail?: string;
}

/** Top predicted FPL performer for a match. */
export interface MatchPlayerImpact {
  element?: number | null;
  name: string;
  position?: string | null;
  team: string;
  expected_points?: number | null;
  fpl_rank_score?: number | null;
  prob_high_score_6?: number | null;
  expected_minutes?: number | null;
  photo_url?: string | null;
  value?: number | null;
}

/** Prediction for a single fixture using the existing Match Model. */
export interface MatchPrediction {
  fixture_id: number;
  code?: number | null;
  gameweek: number;
  kickoff_time?: string | null;
  home_team: string;
  away_team: string;
  home_team_id?: number | null;
  away_team_id?: number | null;
  home_team_logo_url?: string | null;
  away_team_logo_url?: string | null;
  home_win_probability: number;
  draw_probability: number;
  away_win_probability: number;
  predicted_result: "HOME_WIN" | "DRAW" | "AWAY_WIN" | string;
  predicted_home_goals: number;
  predicted_away_goals: number;
  predicted_scoreline: string;
  confidence: number;
  confidence_level: "HIGH" | "MODERATE" | "LOW" | string;
  over_2_5_probability?: number | null;
  under_2_5_probability?: number | null;
  btts_probability?: number | null;
  home_clean_sheet_probability?: number | null;
  away_clean_sheet_probability?: number | null;
  prediction_drivers?: {
    home_attack_strength?: number | null;
    home_defence_strength?: number | null;
    away_attack_strength?: number | null;
    away_defence_strength?: number | null;
    home_form_index?: number | null;
    away_form_index?: number | null;
    home_advantage_active?: boolean | null;
    [key: string]: unknown;
  } | null;
  top_home_players?: MatchPlayerImpact[];
  top_away_players?: MatchPlayerImpact[];
  best_captain_candidate?: MatchPlayerImpact | null;
  best_attacking_option?: MatchPlayerImpact | null;
  best_defensive_option?: MatchPlayerImpact | null;
}

/** GET /match-predictions/next-gameweek response */
export interface MatchPredictionResponse {
  season?: string | null;
  latest_completed_gameweek?: number | null;
  predicted_gameweek?: number | null;
  generated_at?: string | null;
  count: number;
  predictions: MatchPrediction[];
}

/** Player in an optimized squad. */
export interface SquadPlayer {
  element?: number | null;
  name: string;
  position: string;
  team: string;
  price: number;
  value?: number | null;
  predicted_points: number;
  predicted_expected_points?: number | null;
  predicted_fpl_rank_score?: number | null;
  points_per_million: number;
  selection_type: "core" | "value" | "budget_constraint" | string;
  selection_reason: string;
  is_starter: boolean;
  is_captain: boolean;
  is_vice_captain: boolean;
  photo_url?: string | null;
}

/** POST /squad/build or GET /squad/build response */
export interface SquadBuildResponse {
  season?: string | null;
  gameweek?: number | null;
  budget: number;
  total_cost: number;
  remaining_budget: number;
  total_predicted_points: number;
  formation: string;
  count: number;
  captain: SquadPlayer;
  vice_captain: SquadPlayer;
  starting_xi: SquadPlayer[];
  bench: SquadPlayer[];
  squad: SquadPlayer[];
  core_picks: SquadPlayer[];
  value_picks: SquadPlayer[];
}
