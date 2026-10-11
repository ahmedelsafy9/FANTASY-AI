import { motion } from "framer-motion";
import { Sparkles, Calendar, TrendingUp } from "lucide-react";
import type { PlayerRecord } from "@/types/api";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { PlayerAvailabilityBadge } from "@/components/PlayerAvailabilityBadge";
import { UpcomingFixtures } from "@/components/UpcomingFixtures";
import { ExpectedPoints } from "@/components/ExpectedPoints";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { LowOwnershipBadge } from "@/components/LowOwnershipBadge";
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
    <div className="flex flex-col gap-6 pb-6 text-ink-primary">
      {/* Hero card */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="relative overflow-hidden rounded-2xl border border-border bg-ivory-surface p-5 sm:p-6 shadow-card"
      >
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-4">
            <PlayerAvatar
              name={player.name}
              photoUrl={player.photo_url}
              size="xl"
              className="ring-4 ring-gold-metallic/30 shadow-md"
            />
            <div className="min-w-0 flex-1">
              <h2 className="font-display text-2xl sm:text-3xl font-black text-ink-primary leading-tight truncate">
                {player.name ?? "N/A"}
              </h2>
              <div className="mt-1.5 flex flex-wrap items-center gap-2">
                <TeamBadge team={player.team} logoUrl={player.team_logo_url} size="sm" showName />
                {player.position && (
                  <span className="rounded-md bg-stadium-deep text-ivory-surface px-2.5 py-0.5 text-[11px] font-black uppercase">
                    {player.position === "GKP" ? "GK" : player.position}
                  </span>
                )}
                {player.value !== undefined && (
                  <span className="numeral text-xs font-black text-ink-primary bg-ivory-subtle px-2 py-0.5 rounded border border-border">
                    {formatPrice(player.value)}
                  </span>
                )}
                <PlayerAvailabilityBadge player={player} size="sm" />
              </div>
              <div className="mt-2.5 flex items-center gap-2 flex-wrap">
                <ConfidenceBadge level={confidence} />
                <LowOwnershipBadge
                  ownership={player.selected_by_percent ?? (player as Record<string, unknown>).ownership_pct as number | undefined}
                  predictedPoints={xPts}
                />
                <span className="text-xs font-bold text-ink-secondary">
                  • {recommendation}
                </span>
              </div>
            </div>
          </div>

          <div className="flex sm:flex-col items-center sm:items-end justify-between border-t sm:border-t-0 pt-3 sm:pt-0 border-border shrink-0">
            <ExpectedPoints points={xPts} size="lg" />
            {typeof player.predicted_for_gw === "number" && (
              <span className="mt-1 text-[11px] font-bold text-ink-secondary">
                Gameweek {player.predicted_for_gw}
              </span>
            )}
          </div>
        </div>
      </motion.div>

      {/* Explanation Section */}
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
        <h3 className="mb-2.5 flex items-center gap-2 text-xs font-black uppercase tracking-wider text-ink-secondary">
          <Calendar size={14} className="text-gold-metallic" />
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
          <h3 className="mb-2.5 text-xs font-black uppercase tracking-wider text-ink-secondary">
            Form &amp; Tactical Metrics
          </h3>
          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
            {stats.map((s) => (
              <div
                key={s.label}
                className="rounded-xl border border-border bg-ivory-surface px-3.5 py-3 shadow-xs"
              >
                <Stat label={s.label} value={s.value} tone={s.tone} />
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* Key Signals */}
      {insights.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.2 }}
        >
          <h3 className="mb-2.5 flex items-center gap-2 text-xs font-black uppercase tracking-wider text-ink-secondary">
            <Sparkles size={14} className="text-gold-metallic" />
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
        <h3 className="mb-2.5 flex items-center gap-2 text-xs font-black uppercase tracking-wider text-ink-secondary">
          <TrendingUp size={14} className="text-stadium-forest" />
          Performance Trends
        </h3>
        <div className="flex flex-col gap-3">
          <RollingWindowChart player={player} metric="total_points" label="Points" color="#10291F" />
          <RollingWindowChart player={player} metric="minutes" label="Minutes" color="#234735" />
          <RollingWindowChart player={player} metric="xG" label="Expected Goals (xG)" color="#C5A15B" />
          <RollingWindowChart player={player} metric="xA" label="Expected Assists (xA)" color="#9D7A3C" />
        </div>
      </motion.div>

      {/* Progressive Disclosure: Advanced Prediction Details */}
      <AdvancedToggle label="Detailed prediction breakdown">
        <div className="space-y-4 pt-1">
          {/* Haul Likelihood */}
          {(typeof player.prob_high_score_6 === "number" ||
            typeof player.prob_high_score_8 === "number" ||
            typeof player.prob_high_score_10 === "number" ||
            typeof player.prob_high_score_12 === "number") && (
            <div className="rounded-xl border border-border bg-ivory-surface p-4">
              <h4 className="text-xs font-black uppercase tracking-wider text-ink-primary mb-3">
                Haul Potential
              </h4>
              <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
                {[
                  { label: "Chance of 6+ pts (return)", value: player.prob_high_score_6, color: "bg-stadium-forest" },
                  { label: "Chance of 8+ pts", value: player.prob_high_score_8, color: "bg-stadium-deep" },
                  { label: "Chance of 10+ pts (haul)", value: player.prob_high_score_10, color: "bg-gold-metallic" },
                  { label: "Chance of 12+ pts (mega haul)", value: player.prob_high_score_12, color: "bg-gold-bright" },
                ].map((item) => {
                  const pct = typeof item.value === "number" ? Math.round(item.value * 100) : null;
                  return (
                    <div key={item.label} className="rounded-lg border border-border bg-ivory-subtle p-2.5 text-center">
                      <div className="text-[10px] font-bold text-ink-secondary mb-1">{item.label}</div>
                      <div className="numeral text-base font-black text-ink-primary">
                        {pct !== null ? `${pct}%` : "—"}
                      </div>
                      <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-border">
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
            <div className="rounded-xl border border-border bg-ivory-surface p-4">
              <h4 className="text-xs font-black uppercase tracking-wider text-ink-primary mb-3">
                Ceiling &amp; Upside Scenarios
              </h4>
              <div className="grid grid-cols-3 gap-2.5 text-center">
                <div className="rounded-lg border border-border bg-ivory-subtle p-2.5">
                  <span className="block text-[10px] font-bold text-ink-secondary">Solid Floor</span>
                  <span className="font-mono text-base font-black text-ink-primary">
                    {formatStat(player.ceiling_p75 ?? player.predicted_p75_points ?? player.predicted_floor_points)} pts
                  </span>
                </div>
                <div className="rounded-lg border border-gold-border/60 bg-gold-light/40 p-2.5">
                  <span className="block text-[10px] font-bold text-gold-dark">High Upside (P85)</span>
                  <span className="font-mono text-base font-black text-gold-dark">
                    {formatStat(player.ceiling_p85 ?? player.predicted_p85_points)} pts
                  </span>
                </div>
                <div className="rounded-lg border border-gold-border bg-gold-light p-2.5">
                  <span className="block text-[10px] font-bold text-gold-dark">Maximum Ceiling (P90)</span>
                  <span className="font-mono text-base font-black text-gold-dark">
                    {formatStat(player.ceiling_p90 ?? player.predicted_p90_points)} pts
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Points Breakdown */}
          {player.points_breakdown && (
            <div className="rounded-xl border border-border bg-ivory-surface p-4">
              <h4 className="text-xs font-black uppercase tracking-wider text-ink-primary mb-3">
                Expected Points Breakdown
              </h4>
              <div className="flex flex-col gap-2 text-xs">
                <div className="flex justify-between py-1 border-b border-border text-ink-secondary">
                  <span>Appearance points expected</span>
                  <span className="font-mono font-bold text-ink-primary">
                    +{formatStat(player.points_breakdown.appearance_points)} pts
                  </span>
                </div>
                <div className="flex justify-between py-1 border-b border-border text-ink-secondary">
                  <span>Goal points expected</span>
                  <span className="font-mono font-bold text-ink-primary">
                    +{formatStat(player.points_breakdown.goal_points)} pts
                  </span>
                </div>
                <div className="flex justify-between py-1 border-b border-border text-ink-secondary">
                  <span>Assist points expected</span>
                  <span className="font-mono font-bold text-ink-primary">
                    +{formatStat(player.points_breakdown.assist_points)} pts
                  </span>
                </div>
                <div className="flex justify-between py-1 border-b border-border text-ink-secondary">
                  <span>Clean sheet points expected</span>
                  <span className="font-mono font-bold text-ink-primary">
                    +{formatStat(player.points_breakdown.clean_sheet_points)} pts
                  </span>
                </div>
                <div className="flex justify-between py-1 text-ink-secondary">
                  <span>Bonus points expected</span>
                  <span className="font-mono font-bold text-ink-primary">
                    +{formatStat(player.points_breakdown.bonus_points)} pts
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Playing time reliability */}
          <div className="rounded-xl border border-border bg-ivory-surface p-4">
            <h4 className="text-xs font-black uppercase tracking-wider text-ink-primary mb-2">
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
