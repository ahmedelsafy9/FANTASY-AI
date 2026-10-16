import { useCallback, useEffect, useState } from "react"
import { api } from "../api/client"
import { isMockMode } from "../api/config"
import { mapMatch, mapPlayer, mapSquadPlayer } from "../api/adapters"
import {
  matches as sampleMatches,
  players as samplePlayers,
  scenario as sampleScenario,
  type Match,
  type Player,
} from "../data"

export type WizardScenario = {
  completed: number
  target: number
  season: string
  freshness?: string | null
  mock: boolean
}

export type DataStatus = "loading" | "ready" | "error" | "unavailable"

export function useWizardData() {
  const [status, setStatus] = useState<DataStatus>(isMockMode() ? "ready" : "loading")
  const [error, setError] = useState<string | null>(null)
  const [players, setPlayers] = useState<Player[]>(isMockMode() ? samplePlayers : [])
  const [matches, setMatches] = useState<Match[]>(isMockMode() ? sampleMatches : [])
  const [scenario, setScenario] = useState<WizardScenario>({
    ...sampleScenario,
    mock: isMockMode(),
  })
  const [captainId, setCaptainId] = useState<number>(samplePlayers[0]?.id ?? 1)
  const [captainReason, setCaptainReason] = useState("Sample captain projection.")
  const [squadIds, setSquadIds] = useState<number[]>(
    samplePlayers.slice(0, 15).map((player) => player.id),
  )
  const [chatEnabled, setChatEnabled] = useState(false)

  const load = useCallback(async () => {
    if (isMockMode()) {
      setStatus("ready")
      setError(null)
      return
    }
    setStatus("loading")
    setError(null)
    try {
      const [health, predictionList, captain, matchList, squad, chat] =
        await Promise.all([
          api.health(),
          api.predictions(),
          api.captain(),
          api.matches(),
          api.squad().catch(() => null),
          api.chatbotStatus().catch(() => ({ enabled: false, configured: false })),
        ])

      if (health.status !== "ok") {
        setStatus("unavailable")
        setError("The prediction service is not ready.")
        setPlayers([])
        setMatches([])
        return
      }

      const mappedPlayers = predictionList.predictions.map(mapPlayer)
      setPlayers(mappedPlayers)
      setMatches(matchList.predictions.map(mapMatch))
      setScenario({
        completed:
          predictionList.last_completed_gameweek ??
          predictionList.latest_completed_gameweek ??
          health.last_completed_gameweek ??
          0,
        target:
          predictionList.predicted_gameweek ?? health.predicted_gameweek ?? 1,
        season: predictionList.season ?? health.season ?? "",
        freshness: predictionList.data_freshness ?? health.data_freshness,
        mock: false,
      })
      const rec = captain.recommendation
      const capId = Number(rec.element ?? rec.id)
      setCaptainId(Number.isFinite(capId) ? capId : mappedPlayers[0]?.id ?? 1)
      setCaptainReason(captain.reasoning)
      if (squad?.squad?.length) {
        const livePlayers = squad.squad.map(mapSquadPlayer)
        setPlayers((current) => {
          const byId = new Map(current.map((player) => [player.id, player]))
          for (const player of livePlayers) byId.set(player.id, player)
          return Array.from(byId.values()).sort(
            (a, b) => (b.points ?? -1) - (a.points ?? -1),
          )
        })
        setSquadIds(livePlayers.map((player) => player.id))
      } else {
        setSquadIds(mappedPlayers.slice(0, 15).map((player) => player.id))
      }
      setChatEnabled(Boolean(chat.enabled))
      setStatus("ready")
    } catch (err) {
      setStatus("error")
      setError(err instanceof Error ? err.message : "Unable to load predictions.")
      setPlayers([])
      setMatches([])
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return {
    status,
    error,
    players,
    matches,
    scenario,
    captainId,
    captainReason,
    squadIds,
    chatEnabled,
    reload: load,
    sendChat: api.chatbotMessage,
  }
}
