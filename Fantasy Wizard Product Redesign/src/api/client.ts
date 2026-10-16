import { API_BASE_URL } from "./config"
import type {
  CaptainResponse,
  ChatResponse,
  ChatStatusResponse,
  HealthResponse,
  MatchPredictionResponse,
  PredictionListResponse,
  SquadBuildResponse,
} from "./types"

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  })
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = (await response.json()) as { detail?: string }
      if (typeof body.detail === "string") detail = body.detail
    } catch {
      /* keep status text */
    }
    throw new Error(detail || `Request failed (${response.status})`)
  }
  return (await response.json()) as T
}

export const api = {
  health: () => request<HealthResponse>("/health"),
  predictions: () => request<PredictionListResponse>("/predict"),
  captain: () => request<CaptainResponse>("/captain"),
  matches: () => request<MatchPredictionResponse>("/match-predictions/next-gameweek"),
  squad: () =>
    request<SquadBuildResponse>("/squad/build", {
      method: "POST",
      body: JSON.stringify({
        budget: 100,
        formation: "3-5-2",
        core_picks_count: 4,
      }),
    }),
  chatbotStatus: () => request<ChatStatusResponse>("/chatbot/status"),
  chatbotMessage: (message: string, history: { role: string; content: string }[]) =>
    request<ChatResponse>("/chatbot/message", {
      method: "POST",
      body: JSON.stringify({ message, conversation_history: history }),
    }),
}
