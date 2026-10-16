export type HealthResponse = {
  status: string
  model_name?: string | null
  scoring_model?: string | null
  player_count?: number | null
  live_metadata_available?: boolean | null
  season?: string | null
  latest_completed_gameweek?: number | null
  last_completed_gameweek?: number | null
  predicted_gameweek?: number | null
  prediction_cutoff?: string | null
  data_freshness?: string | null
  model_version?: string | null
}

export type PredictionListResponse = {
  count: number
  season?: string | null
  latest_completed_gameweek?: number | null
  last_completed_gameweek?: number | null
  predicted_gameweek?: number | null
  prediction_cutoff?: string | null
  data_freshness?: string | null
  model_version?: string | null
  generated_at?: string | null
  predictions: Record<string, unknown>[]
}

export type CaptainResponse = {
  recommendation: Record<string, unknown>
  reasoning: string
  pool_size: number
}

export type MatchPrediction = {
  fixture_id: number
  gameweek: number
  kickoff_time?: string | null
  home_team: string
  away_team: string
  home_team_logo_url?: string | null
  away_team_logo_url?: string | null
  home_win_probability: number
  draw_probability: number
  away_win_probability: number
  predicted_home_goals?: number
  predicted_away_goals?: number
}

export type MatchPredictionResponse = {
  season?: string | null
  latest_completed_gameweek?: number | null
  predicted_gameweek?: number | null
  count: number
  predictions: MatchPrediction[]
}

export type SquadPlayer = {
  element?: number | null
  name: string
  position: string
  team: string
  price: number
  predicted_points: number
  photo_url?: string | null
  is_captain?: boolean
  is_vice_captain?: boolean
  is_starter?: boolean
}

export type SquadBuildResponse = {
  season?: string | null
  gameweek?: number | null
  budget: number
  total_cost: number
  formation: string
  captain: SquadPlayer
  vice_captain: SquadPlayer
  starting_xi: SquadPlayer[]
  bench: SquadPlayer[]
  squad: SquadPlayer[]
}

export type ChatStatusResponse = {
  enabled: boolean
  configured: boolean
  provider?: string | null
  model?: string | null
}

export type ChatResponse = {
  response: string
  fallback?: boolean
  fallback_reason?: string | null
}
