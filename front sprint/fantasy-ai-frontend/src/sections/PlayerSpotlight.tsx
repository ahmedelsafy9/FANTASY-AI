import { motion } from "framer-motion";
import type { PlayerRecord } from "@/types/api";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { Stat, ConfidenceBar } from "@/components/stats";
import { Badge } from "@/components/ui/primitives";
import { formatPrice, formatStat } from "@/lib/format";
import { deriveInsights, derivePlayingTimeReliability } from "@/lib/insights";
import { EmptyState } from "@/components/states";

interface PlayerSpotlightProps {
  player: PlayerRecord | null;
}

export function PlayerSpotlight({ player }: PlayerSpotlightProps) {
  return (
    <section className="mx-auto max-w-5xl px-5 py-14 lg:px-8">
      <div className="mb-8">
        <h2 className="text-2xl font-semibold text-ink sm:text-3xl">Player Spotlight</h2>
        <p className="mt-1.5 text-sm text-ink-tertiary">
          This Gameweek's highest-projected player, in detail.
        </p>
      </div>

      {!player ? (
        <EmptyState title="No spotlight player available" description="Predictions haven't been generated yet." />
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="grid grid-cols-1 gap-6 rounded-2xl border border-border-soft bg-surface p-6 sm:p-8 lg:grid-cols-[auto_1fr]"
        >
          <div className="flex items-center gap-4 lg:flex-col lg:items-start">
            <PlayerAvatar name={player.name} size="lg" />
            <div>
              <h3 className="font-display text-2xl font-semibold text-ink">{player.name ?? "N/A"}</h3>
              <div className="mt-2">
                <TeamBadge team={player.team} showName />
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-6">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <span className="text-[11px] uppercase tracking-wide text-ink-tertiary">
                  Expected Points
                </span>
                <div className="numeral text-gradient-gold text-5xl font-bold leading-none">
                  {formatStat(player.predicted_total_points)}
                </div>
              </div>
              <div className="w-40">
                <ConfidenceBar value={derivePlayingTimeReliability(player)} />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat label="Form (3gw)" value={formatStat(player.total_points_avg_last_3)} tone="gold" size="md" />
              <Stat label="Minutes (5gw)" value={formatStat(player.minutes_avg_last_5, 0)} tone="signal" size="md" />
              <Stat label="Price" value={formatPrice(player.value)} size="md" />
              <Stat
                label="Fixture"
                value={player.opponent_team ?? "N/A"}
                size="md"
              />
            </div>

            <div className="flex flex-wrap gap-2">
              {deriveInsights(player).map((insight) => (
                <Badge key={insight.label} tone={insight.tone}>
                  {insight.label}
                </Badge>
              ))}
            </div>
          </div>
        </motion.div>
      )}
    </section>
  );
}
