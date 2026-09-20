import { motion } from "framer-motion";
import { Crown, Sparkles, Users, ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import { useCaptain } from "@/hooks/useApi";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { FixtureBadge } from "@/components/FixtureBadge";
import { ExpectedPoints } from "@/components/ExpectedPoints";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { ExplanationSection } from "@/components/ExplanationSection";
import { InsightTag } from "@/components/InsightTag";
import { PlayerCardSkeleton, ErrorState, EmptyState } from "@/components/states";
import { Button } from "@/components/ui/primitives";
import { deriveInsights, deriveConfidenceLevel, deriveReasons } from "@/lib/insights";

export default function Captain() {
  const { data, loading, error, refetch } = useCaptain();

  const player = data?.recommendation;
  const confidence = player ? deriveConfidenceLevel(player) : "HIGH";
  const reasons = player ? deriveReasons(player) : [];
  const playerId = player?.element !== undefined ? String(player.element) : player?.name ?? "";

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 pb-safe-bottom lg:px-8">
      {/* Header */}
      <div className="mb-8 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#FFFBEB] text-[#92400E] border border-[#FDE68A] shadow-sm">
          <Crown size={20} />
        </div>
        <div>
          <h1 className="font-display text-2xl font-black text-[#0F172A] sm:text-3xl">
            Captain Recommendation
          </h1>
          <p className="text-sm font-semibold text-[#475569]">
            The top projected captain pick for maximum 2× points boost this gameweek.
          </p>
        </div>
      </div>

      {loading && (
        <div className="max-w-md mx-auto">
          <PlayerCardSkeleton />
        </div>
      )}

      {!loading && error && <ErrorState message={error} onRetry={refetch} />}

      {!loading && !error && !data && (
        <EmptyState
          title="No captain recommendation available"
          description="Unable to generate captain recommendations at this time."
        />
      )}

      {!loading && !error && data && player && (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="flex flex-col gap-6"
        >
          {/* Captain hero card */}
          <div className="relative overflow-hidden rounded-2xl border border-[#FDE68A] bg-gradient-to-br from-[#FFFBEB] via-white to-[#ECFDF5] shadow-card">
            {/* Top gold stripe */}
            <div className="h-1.5 w-full bg-gradient-to-r from-[#F59E0B] via-[#FBBF24] to-[#10B981]" />

            <div className="flex flex-col items-center gap-5 p-8 text-center sm:p-10">
              {/* Crown icon badge */}
              <motion.div
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ duration: 0.4, delay: 0.1 }}
                className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[#F59E0B] text-[#0F172A] shadow-md border-2 border-white"
              >
                <Crown size={28} />
              </motion.div>

              {/* Player photo */}
              <motion.div
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ duration: 0.4, delay: 0.15 }}
              >
                <PlayerAvatar
                  name={player.name}
                  photoUrl={player.photo_url}
                  size="xl"
                  className="ring-4 ring-[#F59E0B] shadow-card"
                />
              </motion.div>

              {/* Name + team */}
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.2 }}
                className="space-y-2"
              >
                <h2 className="font-display text-3xl font-black text-[#0F172A] sm:text-4xl">
                  {player.name ?? "N/A"}
                </h2>
                <div className="flex items-center justify-center gap-2">
                  <TeamBadge
                    team={player.team}
                    logoUrl={player.team_logo_url}
                    size="md"
                    showName
                  />
                  {player.position && (
                    <span className="rounded-full bg-[#0F172A] px-3 py-0.5 text-xs font-black uppercase text-white shadow-sm">
                      {player.position}
                    </span>
                  )}
                  <ConfidenceBadge level={confidence} />
                </div>
              </motion.div>

              {/* Expected points (2x Captain) */}
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.5, delay: 0.25 }}
                className="flex items-center gap-6 rounded-2xl bg-white border border-[#E2E8F0] p-4 shadow-sm"
              >
                <div className="text-center">
                  <span className="text-[10px] font-black uppercase tracking-wider text-[#64748B] block">
                    Base Projection
                  </span>
                  <ExpectedPoints
                    points={player.predicted_expected_points ?? player.predicted_total_points}
                    size="md"
                    showLabel={false}
                  />
                </div>
                <div className="h-10 w-px bg-[#E2E8F0]" />
                <div className="text-center">
                  <span className="text-[10px] font-black uppercase tracking-wider text-[#D97706] block">
                    As Captain (2×)
                  </span>
                  <span className="font-mono text-3xl font-black text-[#B45309]">
                    {((player.predicted_expected_points ?? player.predicted_total_points ?? 0) * 2).toFixed(1)} pts
                  </span>
                </div>
              </motion.div>

              {/* Fixture */}
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.3 }}
              >
                <FixtureBadge player={player} size="lg" />
              </motion.div>

              <Link to={`/players/${encodeURIComponent(playerId)}`}>
                <Button variant="secondary" size="sm" className="gap-1.5 font-bold mt-1">
                  <span>View Full Player Profile</span>
                  <ArrowRight size={14} />
                </Button>
              </Link>
            </div>
          </div>

          {/* AI Reasoning */}
          {data.reasoning && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.35 }}
              className="rounded-2xl border border-[#A7F3D0] bg-[#ECFDF5] p-5 shadow-sm"
            >
              <h3 className="mb-2 flex items-center gap-2 text-xs font-black uppercase text-[#059669]">
                <Sparkles size={14} />
                Captaincy Assessment
              </h3>
              <p className="text-sm font-semibold leading-relaxed text-[#334155]">
                {data.reasoning}
              </p>
              <div className="mt-3 flex items-center gap-2 text-xs font-bold text-[#64748B]">
                <Users size={14} />
                <span>Selected from {data.pool_size} evaluated Premier League starters</span>
              </div>
            </motion.div>
          )}

          {/* Why this pick? (Deterministic reasons) */}
          {reasons.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.4 }}
            >
              <ExplanationSection reasons={reasons} title="Key Strengths This Gameweek" />
            </motion.div>
          )}

          {/* Insights */}
          {deriveInsights(player).length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.45 }}
            >
              <h3 className="mb-3 text-xs font-black uppercase text-[#64748B]">
                Signal Tags
              </h3>
              <div className="flex flex-wrap gap-2">
                {deriveInsights(player).map((insight) => (
                  <InsightTag key={insight.label} insight={insight} />
                ))}
              </div>
            </motion.div>
          )}
        </motion.div>
      )}
    </div>
  );
}
