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
        className="flex flex-col gap-3 rounded-chunky-lg border-2 border-amber-300 bg-amber-50 p-5 shadow-sm"
      >
        <div className="flex items-end justify-between gap-4">
          <PredictionScore points={player.predicted_expected_points ?? player.predicted_total_points} size="lg" />
          <div className="w-36">
            <ConfidenceBar value={reliability} />
            {typeof player.predicted_for_gw === "number" && (
              <div className="mt-2 text-right text-[11px] font-black text-slate-500">
                GW {player.predicted_for_gw}
              </div>
            )}
          </div>
        </div>

        {/* Distribution / Ceiling / Upside Metrics Strip */}
        {typeof player.predicted_p85_points === "number" && (
          <div className="grid grid-cols-4 gap-2 pt-3 border-t border-amber-200 text-center">
            <div className="rounded-lg bg-white p-2 border border-amber-200">
              <span className="block text-[9px] font-black uppercase text-slate-500">Floor (P10)</span>
              <span className="font-mono text-xs font-black text-slate-700">
                {formatStat(player.predicted_floor_points)}
              </span>
            </div>
            <div className="rounded-lg bg-white p-2 border border-amber-200">
              <span className="block text-[9px] font-black uppercase text-emerald-700">P85 Upside</span>
              <span className="font-mono text-xs font-black text-emerald-700">
                {formatStat(player.predicted_p85_points)}
              </span>
            </div>
            <div className="rounded-lg bg-white p-2 border border-amber-200">
              <span className="block text-[9px] font-black uppercase text-purple-700">P90 Ceiling</span>
              <span className="font-mono text-xs font-black text-purple-700">
                {formatStat(player.predicted_p90_points)}
              </span>
            </div>
            <div className="rounded-lg bg-white p-2 border border-amber-200">
              <span className="block text-[9px] font-black uppercase text-amber-800">Captain Score</span>
              <span className="font-mono text-xs font-black text-amber-800">
                {formatStat(player.captaincy_score)}
              </span>
            </div>
          </div>
        )}
      </motion.div>

      {/* Multi-Task Event & Point Contribution Breakdown */}
      {(player.points_breakdown || typeof player.predicted_goals === "number") && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.08 }}
          className="rounded-chunky-lg border border-slate-200 bg-slate-50 p-4 shadow-sm"
        >
          <h3 className="mb-3 flex items-center justify-between text-xs font-black uppercase tracking-wider text-slate-600">
            <span>Model Contribution Breakdown</span>
            <span className="text-[10px] font-semibold text-slate-400">Deterministic Engine</span>
          </h3>

          {/* Event Expectations */}
          <div className="grid grid-cols-4 gap-2 mb-3 text-center">
            <div className="rounded-lg bg-white p-2 border border-slate-200">
              <span className="block text-[9px] font-black uppercase text-slate-500">Start Prob</span>
              <span className="font-mono text-xs font-black text-slate-700">
                {typeof player.predicted_p_play_60 === "number"
                  ? `${Math.round(player.predicted_p_play_60 * 100)}%`
                  : typeof player.predicted_minutes_60_probability === "number"
                  ? `${Math.round(player.predicted_minutes_60_probability * 100)}%`
                  : "N/A"}
              </span>
            </div>
            <div className="rounded-lg bg-white p-2 border border-slate-200">
              <span className="block text-[9px] font-black uppercase text-slate-500">Exp Goals (xG)</span>
              <span className="font-mono text-xs font-black text-slate-700">
                {formatStat(player.predicted_goals)}
              </span>
            </div>
            <div className="rounded-lg bg-white p-2 border border-slate-200">
              <span className="block text-[9px] font-black uppercase text-slate-500">Exp Assists</span>
              <span className="font-mono text-xs font-black text-slate-700">
                {formatStat(player.predicted_assists)}
              </span>
            </div>
            <div className="rounded-lg bg-white p-2 border border-slate-200">
              <span className="block text-[9px] font-black uppercase text-slate-500">Clean Sheet %</span>
              <span className="font-mono text-xs font-black text-slate-700">
                {typeof player.predicted_clean_sheet_prob === "number"
                  ? `${Math.round(player.predicted_clean_sheet_prob * 100)}%`
                  : typeof player.predicted_clean_sheet_probability === "number"
                  ? `${Math.round(player.predicted_clean_sheet_probability * 100)}%`
                  : "N/A"}
              </span>
            </div>
          </div>

          {/* Points Breakdown */}
          {player.points_breakdown && (
            <div className="flex flex-col gap-1.5 text-xs">
              <div className="flex justify-between py-1 border-b border-slate-200 text-slate-600">
                <span>Appearance Points</span>
                <span className="font-mono font-bold text-slate-800">
                  +{formatStat(player.points_breakdown.appearance_points)} pts
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-200 text-slate-600">
                <span>Goal Points</span>
                <span className="font-mono font-bold text-slate-800">
                  +{formatStat(player.points_breakdown.goal_points)} pts
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-200 text-slate-600">
                <span>Assist Points</span>
                <span className="font-mono font-bold text-slate-800">
                  +{formatStat(player.points_breakdown.assist_points)} pts
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-200 text-slate-600">
                <span>Clean Sheet Points</span>
                <span className="font-mono font-bold text-slate-800">
                  +{formatStat(player.points_breakdown.clean_sheet_points)} pts
                </span>
              </div>
              <div className="flex justify-between py-1 text-slate-600">
                <span>Bonus & Other Points</span>
                <span className="font-mono font-bold text-slate-800">
                  +{formatStat(player.points_breakdown.bonus_points)} pts
                </span>
              </div>
            </div>
          )}
        </motion.div>
      )}

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
