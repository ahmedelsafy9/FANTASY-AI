import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import type { PlayerRecord } from "@/types/api";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { UpcomingFixtures } from "@/components/UpcomingFixtures";
import { PredictionScore } from "@/components/PredictionScore";
import { InsightTag } from "@/components/InsightTag";
import { Stat, ConfidenceBar } from "@/components/stats";
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
  const reliability = derivePlayingTimeReliability(player);

  // Collect available stats — only show what exists
  const stats: { label: string; value: string; tone?: "gold" | "signal" | "teal" | "coral" }[] = [];
  if (player.value !== undefined) stats.push({ label: "Price", value: formatPrice(player.value) });
  if (player.total_points_avg_last_3 !== undefined && player.total_points_avg_last_3 !== null)
    stats.push({ label: "Form (3gw)", value: formatStat(player.total_points_avg_last_3), tone: "gold" });
  if (player.minutes_avg_last_5 !== undefined && player.minutes_avg_last_5 !== null)
    stats.push({ label: "Minutes (5gw)", value: formatStat(player.minutes_avg_last_5, 0), tone: "signal" });
  if (player.total_points !== undefined)
    stats.push({ label: "Last GW pts", value: formatInt(player.total_points), tone: "gold" });
  if (player.bps !== undefined)
    stats.push({ label: "BPS", value: formatInt(player.bps) });
  if (player.ict_index !== undefined)
    stats.push({ label: "ICT Index", value: formatStat(player.ict_index) });
  if (player.xG_avg_last_3 !== undefined && player.xG_avg_last_3 !== null)
    stats.push({ label: "xG (3gw)", value: formatStat(player.xG_avg_last_3, 2), tone: "teal" });
  if (player.xA_avg_last_3 !== undefined && player.xA_avg_last_3 !== null)
    stats.push({ label: "xA (3gw)", value: formatStat(player.xA_avg_last_3, 2), tone: "teal" });
  if (player.rest_days !== undefined)
    stats.push({ label: "Rest days", value: formatInt(player.rest_days) });

  return (
    <div className="flex flex-col gap-6">
      {/* Hero section */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="relative overflow-hidden rounded-xl bg-gradient-to-br from-pitch-dark/60 via-surface to-surface p-5"
      >
        <div className="flex items-center gap-4">
          <PlayerAvatar
            name={player.name}
            photoUrl={player.photo_url}
            size="xl"
            className="ring-2 ring-emerald/20"
          />
          <div className="min-w-0 flex-1">
            <h2 className="font-display text-xl font-bold text-ink leading-tight">
              {player.name ?? "N/A"}
            </h2>
            <div className="mt-2 flex items-center gap-2">
              <TeamBadge team={player.team} logoUrl={player.team_logo_url} size="md" showName />
              {player.position && (
                <span className="rounded bg-white/10 px-2 py-0.5 text-[11px] font-semibold uppercase text-ink-secondary">
                  {player.position}
                </span>
              )}
            </div>
          </div>
        </div>
        {/* Decorative pitch accent */}
        <div
          className="absolute -right-8 -top-8 h-32 w-32 rounded-full bg-emerald/5 blur-2xl"
          aria-hidden="true"
        />
      </motion.div>

      {/* Predicted points + confidence */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.05 }}
        className="flex items-end justify-between gap-4 rounded-xl border border-gold/15 bg-gold/[0.04] p-5"
      >
        <PredictionScore points={player.predicted_total_points} size="lg" />
        <div className="w-36">
          <ConfidenceBar value={reliability} />
          {typeof player.predicted_for_gw === "number" && (
            <div className="mt-2 text-right text-[11px] font-medium text-ink-tertiary">
              GW {player.predicted_for_gw}
            </div>
          )}
        </div>
      </motion.div>

      {/* Fixture section */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
      >
        <h3 className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-ink-tertiary">
          Upcoming Fixtures
        </h3>
        <UpcomingFixtures player={player} variant="full" maxFixtures={5} />
      </motion.div>

      {/* AI Insights */}
      {insights.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.15 }}
        >
          <h3 className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-ink-tertiary">
            <Sparkles size={12} className="text-emerald" />
            AI Insights
          </h3>
          <div className="flex flex-wrap gap-2">
            {insights.map((insight) => (
              <InsightTag key={insight.label} insight={insight} />
            ))}
          </div>
        </motion.div>
      )}

      {/* Key stats grid */}
      {stats.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.2 }}
        >
          <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-ink-tertiary">
            Key Stats
          </h3>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {stats.map((s) => (
              <div
                key={s.label}
                className="rounded-lg border border-border-soft bg-surface-elevated/50 px-3 py-2.5"
              >
                <Stat label={s.label} value={s.value} tone={s.tone} />
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Performance Trends */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.25 }}
      >
        <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-ink-tertiary">
          Performance Trends
        </h3>
        <div className="flex flex-col gap-3">
          <RollingWindowChart player={player} metric="total_points" label="Points" color="#E8B85C" />
          <RollingWindowChart player={player} metric="minutes" label="Minutes" color="#10B981" />
          <RollingWindowChart player={player} metric="xG" label="Expected Goals (xG)" color="#34D1B8" />
          <RollingWindowChart player={player} metric="xA" label="Expected Assists (xA)" color="#E5695A" />
        </div>
      </motion.div>

      {insights.length === 0 && (
        <EmptyState
          title="Prediction explanation not yet available"
          description="Fantasy-AI doesn't yet expose a per-player reasoning breakdown for this record."
        />
      )}
    </div>
  );
}
