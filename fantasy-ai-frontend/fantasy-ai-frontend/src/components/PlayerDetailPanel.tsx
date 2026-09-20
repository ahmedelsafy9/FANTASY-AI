import { motion } from "framer-motion";
import { Sparkles, Calendar, TrendingUp } from "lucide-react";
import type { PlayerRecord } from "@/types/api";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { UpcomingFixtures } from "@/components/UpcomingFixtures";
import { ExpectedPoints } from "@/components/ExpectedPoints";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { ExplanationSection } from "@/components/ExplanationSection";
import { AdvancedToggle } from "@/components/AdvancedToggle";
import { InsightTag } from "@/components/InsightTag";
import { Stat, ConfidenceBar } from "@/components/stats";
import { formatInt, formatPrice, formatStat } from "@/lib/format";
import {
  deriveInsights,
  derivePlayingTimeReliability,
  deriveConfidenceLevel,
  deriveReasons,
  deriveRecommendation,
} from "@/lib/insights";
import { RollingWindowChart } from "@/components/charts/RollingWindowChart";
import { EmptyState } from "@/components/states";

interface PlayerDetailPanelProps {
  player: PlayerRecord;
}

export function PlayerDetailPanel({ player }: PlayerDetailPanelProps) {
  const confidence = deriveConfidenceLevel(player);
  const reasons = deriveReasons(player);
  const recommendation = deriveRecommendation(player, confidence);
  const insights = deriveInsights(player);
  const reliability = derivePlayingTimeReliability(player);
  const xPts = player.predicted_expected_points ?? player.predicted_total_points;

  // Key football stats
  const stats: { label: string; value: string; tone?: "gold" | "signal" | "teal" | "coral" }[] = [];
  if (player.value !== undefined) stats.push({ label: "Price", value: formatPrice(player.value) });
  if (player.total_points_avg_last_3 !== undefined && player.total_points_avg_last_3 !== null)
    stats.push({ label: "Form (3 GW)", value: formatStat(player.total_points_avg_last_3), tone: "gold" });
  if (player.minutes_avg_last_5 !== undefined && player.minutes_avg_last_5 !== null)
    stats.push({ label: "Minutes (5 GW)", value: formatStat(player.minutes_avg_last_5, 0), tone: "signal" });
  if (player.xG_avg_last_3 !== undefined && player.xG_avg_last_3 !== null)
    stats.push({ label: "xG (3 GW)", value: formatStat(player.xG_avg_last_3, 2), tone: "teal" });
  if (player.xA_avg_last_3 !== undefined && player.xA_avg_last_3 !== null)
    stats.push({ label: "xA (3 GW)", value: formatStat(player.xA_avg_last_3, 2), tone: "teal" });
  if (player.total_points !== undefined)
    stats.push({ label: "Last GW pts", value: formatInt(player.total_points), tone: "gold" });
  if (player.bps !== undefined)
    stats.push({ label: "BPS", value: formatInt(player.bps) });
  if (player.ict_index !== undefined)
    stats.push({ label: "ICT Index", value: formatStat(player.ict_index) });
  if (player.rest_days !== undefined)
    stats.push({ label: "Rest days", value: formatInt(player.rest_days) });

  return (
    <div className="flex flex-col gap-6 pb-6">
      {/* Hero card */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="relative overflow-hidden rounded-2xl border border-[#E2E8F0] bg-white p-5 shadow-soft"
      >
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-4">
            <PlayerAvatar
              name={player.name}
              photoUrl={player.photo_url}
              size="xl"
              className="ring-4 ring-[#10B981]/20 shadow-md"
            />
            <div className="min-w-0 flex-1">
              <h2 className="font-display text-2xl font-black text-[#0F172A] leading-tight truncate">
                {player.name ?? "N/A"}
              </h2>
              <div className="mt-1.5 flex flex-wrap items-center gap-2">
                <TeamBadge team={player.team} logoUrl={player.team_logo_url} size="sm" showName />
                {player.position && (
                  <span className="rounded-full bg-[#F1F5F9] border border-[#CBD5E1] px-2.5 py-0.5 text-[11px] font-black uppercase text-[#334155]">
                    {player.position === "GKP" ? "GK" : player.position}
                  </span>
                )}
                {player.value !== undefined && (
                  <span className="numeral text-xs font-black text-[#059669] bg-[#ECFDF5] px-2 py-0.5 rounded border border-[#A7F3D0]">
                    {formatPrice(player.value)}
                  </span>
                )}
              </div>
              <div className="mt-2 flex items-center gap-2">
                <ConfidenceBadge level={confidence} />
                <span className="text-xs font-bold text-[#64748B]">
                  • {recommendation}
                </span>
              </div>
            </div>
          </div>

          <div className="flex sm:flex-col items-center sm:items-end justify-between border-t sm:border-t-0 pt-3 sm:pt-0 border-[#F1F5F9] shrink-0">
            <ExpectedPoints points={xPts} size="lg" />
            {typeof player.predicted_for_gw === "number" && (
              <span className="mt-1 text-[11px] font-bold text-[#64748B]">
                Gameweek {player.predicted_for_gw}
              </span>
            )}
          </div>
        </div>
      </motion.div>

      {/* Why this player? (Explanation Section) */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.05 }}
      >
        <ExplanationSection reasons={reasons} />
      </motion.div>

      {/* Upcoming Fixtures */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.1 }}
      >
        <h3 className="mb-2.5 flex items-center gap-2 text-xs font-black uppercase tracking-wider text-[#475569]">
          <Calendar size={14} className="text-[#10B981]" />
          Upcoming Fixtures
        </h3>
        <UpcomingFixtures player={player} variant="full" maxFixtures={5} />
      </motion.div>

      {/* Key stats grid */}
      {stats.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.15 }}
        >
          <h3 className="mb-2.5 text-xs font-black uppercase tracking-wider text-[#475569]">
            Form & Key Stats
          </h3>
          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
            {stats.map((s) => (
              <div
                key={s.label}
                className="rounded-xl border border-[#E2E8F0] bg-white px-3.5 py-3 shadow-soft"
              >
                <Stat label={s.label} value={s.value} tone={s.tone} />
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* AI Intelligence Insights (if any) */}
      {insights.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.2 }}
        >
          <h3 className="mb-2.5 flex items-center gap-2 text-xs font-black uppercase tracking-wider text-[#475569]">
            <Sparkles size={14} className="text-[#10B981]" />
            Key Signals
          </h3>
          <div className="flex flex-wrap gap-2">
            {insights.map((insight) => (
              <InsightTag key={insight.label} insight={insight} />
            ))}
          </div>
        </motion.div>
      )}

      {/* Performance Trends */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.25 }}
      >
        <h3 className="mb-2.5 flex items-center gap-2 text-xs font-black uppercase tracking-wider text-[#475569]">
          <TrendingUp size={14} className="text-[#10B981]" />
          Performance Trends
        </h3>
        <div className="flex flex-col gap-3">
          <RollingWindowChart player={player} metric="total_points" label="Points" color="#D97706" />
          <RollingWindowChart player={player} metric="minutes" label="Minutes" color="#059669" />
          <RollingWindowChart player={player} metric="xG" label="Expected Goals (xG)" color="#0284C7" />
          <RollingWindowChart player={player} metric="xA" label="Expected Assists (xA)" color="#DC2626" />
        </div>
      </motion.div>

      {/* Progressive Disclosure: Advanced Prediction Details */}
      <AdvancedToggle label="Detailed prediction breakdown">
        <div className="space-y-4 pt-1">
          {/* Haul Likelihood (converted to football terms) */}
          {(typeof player.prob_high_score_6 === "number" ||
            typeof player.prob_high_score_8 === "number" ||
            typeof player.prob_high_score_10 === "number" ||
            typeof player.prob_high_score_12 === "number") && (
            <div className="rounded-xl border border-[#E2E8F0] bg-white p-4">
              <h4 className="text-xs font-black uppercase tracking-wider text-[#0F172A] mb-3">
                Haul Potential
              </h4>
              <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
                {[
                  { label: "Chance of 6+ pts (return)", value: player.prob_high_score_6, color: "bg-[#10B981]" },
                  { label: "Chance of 8+ pts", value: player.prob_high_score_8, color: "bg-[#059669]" },
                  { label: "Chance of 10+ pts (haul)", value: player.prob_high_score_10, color: "bg-[#6366F1]" },
                  { label: "Chance of 12+ pts (mega haul)", value: player.prob_high_score_12, color: "bg-[#8B5CF6]" },
                ].map((item) => {
                  const pct = typeof item.value === "number" ? Math.round(item.value * 100) : null;
                  return (
                    <div key={item.label} className="rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] p-2.5 text-center">
                      <div className="text-[10px] font-bold text-[#64748B] mb-1">{item.label}</div>
                      <div className="numeral text-base font-black text-[#0F172A]">
                        {pct !== null ? `${pct}%` : "—"}
                      </div>
                      <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-[#E2E8F0]">
                        <div
                          className={`h-full rounded-full ${item.color}`}
                          style={{ width: `${pct ?? 0}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Upside / Ceiling Estimates */}
          {(typeof player.ceiling_p85 === "number" || typeof player.predicted_p85_points === "number") && (
            <div className="rounded-xl border border-[#E2E8F0] bg-white p-4">
              <h4 className="text-xs font-black uppercase tracking-wider text-[#0F172A] mb-3">
                Ceiling & Upside Scenarios
              </h4>
              <div className="grid grid-cols-3 gap-2.5 text-center">
                <div className="rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] p-2.5">
                  <span className="block text-[10px] font-bold text-[#64748B]">Solid Floor</span>
                  <span className="font-mono text-base font-black text-[#0F172A]">
                    {formatStat(player.ceiling_p75 ?? player.predicted_p75_points ?? player.predicted_floor_points)} pts
                  </span>
                </div>
                <div className="rounded-lg border border-[#A7F3D0] bg-[#ECFDF5] p-2.5">
                  <span className="block text-[10px] font-bold text-[#059669]">High Upside (P85)</span>
                  <span className="font-mono text-base font-black text-[#059669]">
                    {formatStat(player.ceiling_p85 ?? player.predicted_p85_points)} pts
                  </span>
                </div>
                <div className="rounded-lg border border-[#DDD6FE] bg-[#F5F3FF] p-2.5">
                  <span className="block text-[10px] font-bold text-[#7C3AED]">Maximum Ceiling (P90)</span>
                  <span className="font-mono text-base font-black text-[#7C3AED]">
                    {formatStat(player.ceiling_p90 ?? player.predicted_p90_points)} pts
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Points Breakdown */}
          {player.points_breakdown && (
            <div className="rounded-xl border border-[#E2E8F0] bg-white p-4">
              <h4 className="text-xs font-black uppercase tracking-wider text-[#0F172A] mb-3">
                Expected Points Breakdown
              </h4>
              <div className="flex flex-col gap-2 text-xs">
                <div className="flex justify-between py-1 border-b border-[#F1F5F9] text-[#475569]">
                  <span>Appearance points expected</span>
                  <span className="font-mono font-bold text-[#0F172A]">
                    +{formatStat(player.points_breakdown.appearance_points)} pts
                  </span>
                </div>
                <div className="flex justify-between py-1 border-b border-[#F1F5F9] text-[#475569]">
                  <span>Goal points expected</span>
                  <span className="font-mono font-bold text-[#0F172A]">
                    +{formatStat(player.points_breakdown.goal_points)} pts
                  </span>
                </div>
                <div className="flex justify-between py-1 border-b border-[#F1F5F9] text-[#475569]">
                  <span>Assist points expected</span>
                  <span className="font-mono font-bold text-[#0F172A]">
                    +{formatStat(player.points_breakdown.assist_points)} pts
                  </span>
                </div>
                <div className="flex justify-between py-1 border-b border-[#F1F5F9] text-[#475569]">
                  <span>Clean sheet points expected</span>
                  <span className="font-mono font-bold text-[#0F172A]">
                    +{formatStat(player.points_breakdown.clean_sheet_points)} pts
                  </span>
                </div>
                <div className="flex justify-between py-1 text-[#475569]">
                  <span>Bonus points expected</span>
                  <span className="font-mono font-bold text-[#0F172A]">
                    +{formatStat(player.points_breakdown.bonus_points)} pts
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Playing time reliability */}
          <div className="rounded-xl border border-[#E2E8F0] bg-white p-4">
            <h4 className="text-xs font-black uppercase tracking-wider text-[#0F172A] mb-2">
              Playing Time Security
            </h4>
            <ConfidenceBar value={reliability} label="Minutes Reliability" />
          </div>
        </div>
      </AdvancedToggle>

      {reasons.length === 0 && insights.length === 0 && (
        <EmptyState
          title="Limited player data"
          description="Detailed prediction signals are still compiling for this player."
        />
      )}
    </div>
  );
}
