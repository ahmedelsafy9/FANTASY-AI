import { motion } from "framer-motion";
import type { PlayerRecord } from "@/types/api";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { PredictionScore } from "@/components/PredictionScore";
import { FixtureBadge } from "@/components/FixtureBadge";
import { InsightTag } from "@/components/InsightTag";
import { ConfidenceBar } from "@/components/stats";
import { formatPrice, formatStat } from "@/lib/format";
import { deriveInsights, derivePlayingTimeReliability } from "@/lib/insights";
import { EmptyState } from "@/components/states";

interface PlayerSpotlightProps {
  player: PlayerRecord | null;
}

export function PlayerSpotlight({ player }: PlayerSpotlightProps) {
  return (
    <section className="mx-auto max-w-5xl px-5 py-10 lg:px-8">
      <div className="mb-6">
        <h2 className="font-display text-xl font-bold text-ink sm:text-2xl">Player Spotlight</h2>
        <p className="mt-1 text-sm text-ink-tertiary">
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
          className="grid grid-cols-1 gap-6 rounded-xl border border-border-soft bg-surface p-5 sm:p-6 lg:grid-cols-[auto_1fr]"
        >
          <div className="flex items-center gap-4 lg:flex-col lg:items-start">
            <PlayerAvatar name={player.name} photoUrl={player.photo_url} size="xl" className="ring-2 ring-emerald/20" />
            <div>
              <h3 className="font-display text-xl font-bold text-ink">{player.name ?? "N/A"}</h3>
              <div className="mt-2 flex items-center gap-2">
                <TeamBadge team={player.team} logoUrl={player.team_logo_url} showName size="md" />
                {player.position && (
                  <span className="rounded bg-white/10 px-2 py-0.5 text-[11px] font-semibold uppercase text-ink-secondary">
                    {player.position}
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-5">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <PredictionScore points={player.predicted_total_points} size="lg" />
              <div className="w-40">
                <ConfidenceBar value={derivePlayingTimeReliability(player)} />
              </div>
            </div>

            <FixtureBadge player={player} size="md" />

            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <StatBlock label="Form (3gw)" value={formatStat(player.total_points_avg_last_3)} />
              <StatBlock label="Minutes (5gw)" value={formatStat(player.minutes_avg_last_5, 0)} />
              <StatBlock label="Price" value={formatPrice(player.value)} />
              <StatBlock label="Opponent" value={player.opponent_team ?? "N/A"} />
            </div>

            {deriveInsights(player).length > 0 && (
              <div className="flex flex-wrap gap-2">
                {deriveInsights(player).map((insight) => (
                  <InsightTag key={insight.label} insight={insight} />
                ))}
              </div>
            )}
          </div>
        </motion.div>
      )}
    </section>
  );
}

function StatBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border-soft bg-surface-elevated/50 px-3 py-2">
      <div className="text-[9px] font-medium uppercase tracking-wider text-ink-tertiary">{label}</div>
      <div className="numeral text-sm font-semibold text-ink">{value}</div>
    </div>
  );
}
