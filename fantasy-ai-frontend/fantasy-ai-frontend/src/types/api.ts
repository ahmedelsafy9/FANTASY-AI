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
}

/** Shape of a FastAPI HTTPException error body, e.g. { "detail": "..." } */
export interface ApiErrorBody {
  detail?: string;
}
