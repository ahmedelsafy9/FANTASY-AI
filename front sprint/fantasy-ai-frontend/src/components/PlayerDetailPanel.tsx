import type { PlayerRecord } from "@/types/api";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { Stat, ConfidenceBar } from "@/components/stats";
import { Badge } from "@/components/ui/primitives";
import { formatInt, formatPrice, formatStat } from "@/lib/format";
import { deriveInsights, derivePlayingTimeReliability } from "@/lib/insights";
import { RollingWindowChart } from "@/components/charts/RollingWindowChart";
import { EmptyState } from "@/components/states";

interface PlayerDetailPanelProps {
  player: PlayerRecord;
}

/** Full player profile: identity, key stats, honest AI insights, and
 * rolling-window charts for whichever metrics the backend actually provided. */
export function PlayerDetailPanel({ player }: PlayerDetailPanelProps) {
  const insights = deriveInsights(player);

  return (
    <div className="flex flex-col gap-8">
      <div className="flex items-center gap-4">
        <PlayerAvatar name={player.name} size="lg" />
        <div>
          <h2 className="font-display text-xl font-semibold text-ink">{player.name ?? "N/A"}</h2>
          <div className="mt-1.5 flex items-center gap-2">
            <TeamBadge team={player.team} showName />
            {player.position && <span className="text-xs text-ink-tertiary">· {player.position}</span>}
          </div>
        </div>
      </div>

      <div>
        <span className="text-[11px] uppercase tracking-wide text-ink-tertiary">Expected Points</span>
        <div className="numeral text-gradient-gold text-6xl font-bold leading-none">
          {formatStat(player.predicted_total_points)}
        </div>
        <div className="mt-3 max-w-[200px]">
          <ConfidenceBar value={derivePlayingTimeReliability(player)} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Stat label="Price" value={formatPrice(player.value)} size="md" />
        <Stat label="Upcoming GW" value={player.predicted_for_gw ? `GW ${player.predicted_for_gw}` : "N/A"} size="md" />
        <Stat label="Fixture" value={player.opponent_team ?? "N/A"} size="md" tone="signal" />
        <Stat
          label="Venue"
          value={player.is_home === 1 ? "Home" : player.is_home === 0 ? "Away" : "N/A"}
          size="md"
        />
        <Stat label="Last GW points" value={formatInt(player.total_points)} size="md" tone="gold" />
        <Stat label="Rest days" value={formatInt(player.rest_days)} size="md" />
      </div>

      {insights.length > 0 && (
        <div>
          <h3 className="mb-2.5 text-xs font-semibold uppercase tracking-wide text-ink-tertiary">
            AI Insights
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {insights.map((insight) => (
              <Badge key={insight.label} tone={insight.tone}>
                {insight.label}
              </Badge>
            ))}
          </div>
        </div>
      )}

      <div>
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-ink-tertiary">
          Performance Trends
        </h3>
        <div className="flex flex-col gap-4">
          <RollingWindowChart player={player} metric="total_points" label="Points" color="#E8B85C" />
          <RollingWindowChart player={player} metric="minutes" label="Minutes" color="#7C86FF" />
          <RollingWindowChart player={player} metric="xG" label="Expected Goals (xG)" color="#34D1B8" />
          <RollingWindowChart player={player} metric="xA" label="Expected Assists (xA)" color="#E5695A" />
        </div>
      </div>

      {insights.length === 0 && (
        <EmptyState
          title="Prediction explanation not yet available"
          description="Fantasy-AI doesn't yet expose a per-player reasoning breakdown for this record."
        />
      )}
    </div>
  );
}
