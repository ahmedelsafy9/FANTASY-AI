import type { Match, Player } from "../data"
import type { MatchPrediction, SquadPlayer } from "./types"

function asNumber(value: unknown, fallback = 0): number {
  const n = typeof value === "number" ? value : Number(value)
  return Number.isFinite(n) ? n : fallback
}

function asString(value: unknown, fallback = ""): string {
  return value == null ? fallback : String(value)
}

export function mapAvailability(row: Record<string, unknown>): string {
  const status = asString(row.availability_status).toLowerCase()
  if (row.injury_flag === true || status === "injured") return "Injured"
  if (row.doubt_flag === true || status === "doubt" || status === "doubtful") {
    return "Doubtful"
  }
  if (row.ruled_out_flag === true || status === "unavailable") return "Injured"
  if (status === "unknown" || status === "") return "Unknown"
  return "Available"
}

export function mapPlayer(row: Record<string, unknown>, index: number): Player {
  const id = asNumber(row.element ?? row.id, index + 1)
  const opponent = asString(row.opponent_team || row.next_opponent || "")
  const isHome = row.is_home === true || row.was_home === true
  const fixture = opponent
    ? `${opponent.slice(0, 3).toUpperCase()} (${isHome ? "H" : "A"})`
    : "TBC"
  const pointsRaw =
    row.predicted_expected_points ??
    row.predicted_total_points ??
    row.predicted_fpl_rank_score
  const points =
    pointsRaw == null || pointsRaw === "" ? null : asNumber(pointsRaw)
  const photoCode = asString(row.photo || "").replace(".png", "")
  const photo =
    asString(row.photo_url) ||
    (photoCode
      ? `https://resources.premierleague.com/premierleague/photos/players/250x250/p${photoCode}.png`
      : "")
  return {
    id,
    name: asString(row.name || row.web_name, `Player ${id}`),
    club: asString(row.team, "Unknown"),
    position: asString(row.position, "MID"),
    points,
    status: mapAvailability(row),
    fixture,
    price: asNumber(row.value ?? row.price, asNumber(row.now_cost, 0) / 10),
    ownership: asNumber(row.selected_by_percent ?? row.ownership, 0),
    photo,
  }
}

export function mapMatch(row: MatchPrediction, index: number): Match {
  const kickoff = row.kickoff_time
    ? new Date(row.kickoff_time).toUTCString().replace("GMT", "").trim()
    : "TBC"
  const homePct = Math.round(row.home_win_probability * 100)
  const drawPct = Math.round(row.draw_probability * 100)
  const awayPct = Math.max(0, 100 - homePct - drawPct)
  return {
    home: row.home_team,
    away: row.away_team,
    short: [row.home_team.slice(0, 3).toUpperCase(), row.away_team.slice(0, 3).toUpperCase()],
    crests: [0, 0],
    probabilities: [homePct, drawPct, awayPct] as [number, number, number],
    time: kickoff,
    venue: "",
    homeCrest: row.home_team_logo_url ?? undefined,
    awayCrest: row.away_team_logo_url ?? undefined,
    key: row.fixture_id || index,
  }
}

export function mapSquadPlayer(row: SquadPlayer, index: number): Player {
  return mapPlayer(
    {
      element: row.element,
      name: row.name,
      team: row.team,
      position: row.position,
      predicted_expected_points: row.predicted_points,
      value: row.price,
      photo_url: row.photo_url,
    },
    index,
  )
}

export function padGameweek(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—"
  return String(value).padStart(2, "0")
}
