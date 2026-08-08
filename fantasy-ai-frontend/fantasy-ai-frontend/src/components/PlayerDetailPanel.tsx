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

export function PlayerDetailPanel({ player }: PlayerDetailPanelProps) {
  const insights = deriveInsights(player);
  const reliability = derivePlayingTimeReliability(player);

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
        className="relative overflow-hidden rounded-chunky-lg border-2 border-slate-200 bg-gradient-to-br from-emerald-50 via-white to-amber-50 p-5 shadow-card"
      >
        <div className="flex items-center gap-4">
          <PlayerAvatar
            name={player.name}
            photoUrl={player.photo_url}
            size="xl"
            className="ring-4 ring-emerald-400 shadow-card"
          />
          <div className="min-w-0 flex-1">
            <h2 className="font-display text-2xl font-black text-slate-900 leading-tight">
              {player.name ?? "N/A"}
            </h2>
            <div className="mt-2 flex items-center gap-2">
              <TeamBadge team={player.team} logoUrl={player.team_logo_url} size="md" showName />
              {player.position && (
                <span className="rounded-full bg-slate-900 px-2.5 py-0.5 text-[11px] font-black uppercase text-white shadow-sm">
                  {player.position}
                </span>
              )}
            </div>
          </div>
        </div>
      </motion.div>

      {/* Predicted points + confidence */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.05 }}
        className="flex items-end justify-between gap-4 rounded-chunky-lg border-2 border-amber-300 bg-amber-50 p-5 shadow-sm"
      >
        <PredictionScore points={player.predicted_total_points} size="lg" />
        <div className="w-36">
          <ConfidenceBar value={reliability} />
          {typeof player.predicted_for_gw === "number" && (
            <div className="mt-2 text-right text-[11px] font-black text-slate-500">
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
        <h3 className="mb-2.5 text-xs font-black uppercase tracking-wider text-slate-500">
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
          <h3 className="mb-3 flex items-center gap-2 text-xs font-black uppercase tracking-wider text-slate-500">
            <Sparkles size={14} className="text-emerald-600" />
            AI Intelligence Insights
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
          <h3 className="mb-3 text-xs font-black uppercase tracking-wider text-slate-500">
            Key Stats
          </h3>
          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
            {stats.map((s) => (
              <div
                key={s.label}
                className="rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-3 shadow-sm"
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
        <h3 className="mb-3 text-xs font-black uppercase tracking-wider text-slate-500">
          Performance Trends
        </h3>
        <div className="flex flex-col gap-3">
          <RollingWindowChart player={player} metric="total_points" label="Points" color="#D97706" />
          <RollingWindowChart player={player} metric="minutes" label="Minutes" color="#059669" />
          <RollingWindowChart player={player} metric="xG" label="Expected Goals (xG)" color="#0284C7" />
          <RollingWindowChart player={player} metric="xA" label="Expected Assists (xA)" color="#DC2626" />
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
