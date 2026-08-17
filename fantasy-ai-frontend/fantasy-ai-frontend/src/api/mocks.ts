import type {
  CaptainResponse,
  HealthResponse,
  PlayerRecord,
  PlayerResponse,
  PredictionListResponse,
} from "@/types/api";

/**
 * Mock mode exists ONLY so the frontend can be developed without a running
 * backend. It is opt-in via `VITE_USE_MOCKS=true` and is never used as a
 * silent fallback when a real request fails — a failed request always shows
 * an error state instead (see `ErrorState` and the page-level hooks).
 *
 * The shape of this data mirrors the real backend's response shapes
 * exactly (same field names as `types/api.ts`), so switching mock mode off
 * requires no component changes.
 */
export function isMockMode(): boolean {
  return import.meta.env.VITE_USE_MOCKS === "true";
}

const MOCK_PLAYERS: PlayerRecord[] = [
  {
    element: 1,
    name: "M.Salah",
    team: "Liverpool",
    opponent_team: "Bournemouth",
    season: "2024-25",
    GW: 24,
    predicted_for_gw: 25,
    value: 129,
    total_points: 11,
    minutes: 90,
    was_home: true,
    is_home: 1,
    rest_days: 7,
    team_strength: 6.2,
    opponent_strength: 3.1,
    form_index: 7.8,
    total_points_avg_last_3: 8.7,
    total_points_avg_last_5: 7.9,
    total_points_avg_last_10: 7.1,
    minutes_avg_last_5: 88,
    predicted_total_points: 8.7,
  },
  {
    element: 2,
    name: "E.Haaland",
    team: "Man City",
    opponent_team: "Everton",
    season: "2024-25",
    GW: 24,
    predicted_for_gw: 25,
    value: 151,
    total_points: 9,
    minutes: 82,
    was_home: false,
    is_home: 0,
    rest_days: 6,
    team_strength: 6.8,
    opponent_strength: 2.9,
    form_index: 8.1,
    total_points_avg_last_3: 9.2,
    total_points_avg_last_5: 8.4,
    total_points_avg_last_10: 8.0,
    minutes_avg_last_5: 84,
    predicted_total_points: 8.2,
  },
  {
    element: 3,
    name: "B.Saka",
    team: "Arsenal",
    opponent_team: "Fulham",
    season: "2024-25",
    GW: 24,
    predicted_for_gw: 25,
    value: 101,
    total_points: 6,
    minutes: 90,
    was_home: true,
    is_home: 1,
    rest_days: 8,
    team_strength: 5.9,
    opponent_strength: 3.4,
    form_index: 6.9,
    total_points_avg_last_3: 6.5,
    total_points_avg_last_5: 6.1,
    total_points_avg_last_10: 6.4,
    minutes_avg_last_5: 87,
    predicted_total_points: 7.1,
  },
];

const MOCK_HEALTH: HealthResponse = {
  status: "ok",
  model_name: "random_forest",
  player_count: MOCK_PLAYERS.length,
};

const MOCK_CAPTAIN: CaptainResponse = {
  recommendation: MOCK_PLAYERS[0],
  reasoning:
    "Highest predicted scorer among players averaging at least 60 minutes recently (minutes_avg_last_5).",
  pool_size: MOCK_PLAYERS.length,
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function getMock(kind: string, arg?: string): any {
  // eslint-disable-next-line no-console
  console.warn(
    `%c[Fantasy-AI] MOCK MODE ACTIVE — serving fake "${kind}" data. Set VITE_USE_MOCKS=false to use the real backend.`,
    "color:#E8B85C;font-weight:600;",
  );

  switch (kind) {
    case "health":
      return MOCK_HEALTH satisfies HealthResponse;
    case "player": {
      const found = MOCK_PLAYERS.find((p) => String(p.element) === arg);
      return { data: found ?? MOCK_PLAYERS[0] } satisfies PlayerResponse;
    }
    case "predict": {
      const list = arg ? MOCK_PLAYERS.filter((p) => String(p.element) === arg) : MOCK_PLAYERS;
      return {
        count: list.length,
        predicted_for_gw_note:
          "predicted for gw reflects each player's own most recent match, so it may differ slightly between players who have played a different number of games.",
        predictions: list,
      } satisfies PredictionListResponse;
    }
    case "top_players": {
      const limit = arg ? Number(arg) : 10;
      const list = MOCK_PLAYERS.slice(0, limit);
      return {
        count: list.length,
        predicted_for_gw_note:
          "predicted for gw reflects each player's own most recent match, so it may differ slightly between players who have played a different number of games.",
        predictions: list,
      } satisfies PredictionListResponse;
    }
    case "captain":
      return MOCK_CAPTAIN satisfies CaptainResponse;
    default:
      throw new Error(`Unknown mock kind: ${kind}`);
  }
}
