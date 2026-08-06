import { apiClient } from "./client";
import { getMock, isMockMode } from "./mocks";
import type {
  CaptainResponse,
  HealthResponse,
  PlayerResponse,
  PredictionListResponse,
} from "@/types/api";

/**
 * Every function here maps 1:1 to a real backend route (see the backend's
 * `src/api/routers/*.py`). No endpoint is invented. Mock mode (see
 * `mocks.ts`) is an explicit, clearly-logged opt-in for local frontend
 * development without a running backend — it is never a silent fallback
 * when a real request fails.
 */

export async function getHealth(): Promise<HealthResponse> {
  if (isMockMode()) return getMock("health");
  const { data } = await apiClient.get<HealthResponse>("/");
  return data;
}

export async function getPlayer(playerId: string): Promise<PlayerResponse> {
  if (isMockMode()) return getMock("player", playerId);
  const { data } = await apiClient.get<PlayerResponse>(`/player/${encodeURIComponent(playerId)}`);
  return data;
}

export async function getPredictions(playerId?: string): Promise<PredictionListResponse> {
  if (isMockMode()) return getMock("predict", playerId);
  const { data } = await apiClient.get<PredictionListResponse>("/predict", {
    params: playerId ? { player_id: playerId } : undefined,
  });
  return data;
}

export async function getTopPlayers(limit = 10): Promise<PredictionListResponse> {
  if (isMockMode()) return getMock("top_players", String(limit));
  const { data } = await apiClient.get<PredictionListResponse>("/top_players", {
    params: { limit },
  });
  return data;
}

export async function getCaptain(): Promise<CaptainResponse> {
  if (isMockMode()) return getMock("captain");
  const { data } = await apiClient.get<CaptainResponse>("/captain");
  return data;
}
