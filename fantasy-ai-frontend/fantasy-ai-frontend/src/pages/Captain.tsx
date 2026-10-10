import { motion } from "framer-motion";
import { Crown, Sparkles, Users, ArrowRight, ShieldCheck } from "lucide-react";
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
  const basePoints = Math.round(player?.predicted_expected_points ?? player?.predicted_total_points ?? 0);
  const captainPoints = basePoints * 2;

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 pb-safe-bottom lg:px-8">
      {/* Broadcast Header */}
      <div className="mb-8 flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#FDF8EC] text-[#8C680E] border border-[#E5D08E] shadow-sm">
          <Crown size={22} />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-display text-2xl font-black text-[#19171D] sm:text-3xl tracking-tight">
              Captaincy Hub
            </h1>
            <span className="rounded-full bg-[#EEE7FA] px-2.5 py-0.5 text-[10px] font-black uppercase text-[#452477] border border-[#D5C6F0]">
              2× Points Multiplier
            </span>
          </div>
          <p className="text-xs sm:text-sm font-semibold text-[#6F6A76] mt-0.5">
            The top projected captain pick for maximum gameweek points boost.
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
          {/* Captain Hero Card */}
          <div className="relative overflow-hidden rounded-2xl border border-[#E8E3ED] bg-white shadow-card">
            {/* Top EPL purple broadcast stripe */}
            <div className="h-2 w-full bg-gradient-to-r from-[#452477] via-[#7041C5] to-[#B58A18]" />

            <div className="flex flex-col items-center gap-5 p-8 text-center sm:p-10">
              {/* Captain Armband Emblem */}
              <motion.div
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ duration: 0.4, delay: 0.1 }}
                className="flex items-center gap-2 rounded-full bg-[#FDF8EC] px-4 py-1.5 border border-[#E5D08E] shadow-xs"
              >
                <Crown size={16} className="text-[#8C680E]" />
                <span className="text-xs font-black uppercase tracking-wider text-[#8C680E]">
                  Official Armband Pick
                </span>
              </motion.div>

              {/* Player photo */}
              <motion.div
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ duration: 0.4, delay: 0.15 }}
                className="relative"
              >
                <PlayerAvatar
                  name={player.name}
                  photoUrl={player.photo_url}
                  size="xl"
                  className="ring-4 ring-[#7041C5]/30 shadow-card"
                />
                <div className="absolute -bottom-1 -right-1 flex h-7 w-7 items-center justify-center rounded-full bg-[#B58A18] text-white font-black text-xs shadow-md border-2 border-white">
                  C
                </div>
              </motion.div>

              {/* Name + team */}
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.2 }}
                className="space-y-2"
              >
                <h2 className="font-display text-3xl font-black text-[#19171D] sm:text-4xl">
                  {player.name ?? "N/A"}
                </h2>
                <div className="flex items-center justify-center gap-2 flex-wrap">
                  <TeamBadge
                    team={player.team}
                    logoUrl={player.team_logo_url}
                    size="md"
                    showName
                  />
                  {player.position && (
                    <span className="rounded-full bg-[#452477] px-3 py-0.5 text-xs font-black uppercase text-white shadow-xs">
                      {player.position}
                    </span>
                  )}
                  <ConfidenceBadge level={confidence} />
                </div>
              </motion.div>

              {/* Expected points (2x Captain) comparison tiles */}
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.5, delay: 0.25 }}
                className="flex items-center gap-6 sm:gap-10 rounded-2xl bg-[#F8F7FA] border border-[#E8E3ED] p-5 shadow-xs"
              >
                <div className="text-center">
                  <span className="text-[10px] font-black uppercase tracking-wider text-[#6F6A76] block">
                    Base Projection
                  </span>
                  <ExpectedPoints
                    points={basePoints}
                    size="md"
                    showLabel={false}
                  />
                </div>
                <div className="h-10 w-px bg-[#E8E3ED]" />
                <div className="text-center">
                  <span className="text-[10px] font-black uppercase tracking-wider text-[#8C680E] block">
                    As Captain (2×)
                  </span>
                  <span className="font-mono text-3xl sm:text-4xl font-black text-[#8C680E]">
                    {captainPoints} <span className="text-base sm:text-lg font-bold">pts</span>
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
              className="rounded-2xl border border-[#D5C6F0] bg-[#EEE7FA] p-5 sm:p-6 shadow-sm"
            >
              <h3 className="mb-2 flex items-center gap-2 text-xs font-black uppercase text-[#452477] tracking-wider">
                <Sparkles size={15} />
                AI Captaincy Assessment
              </h3>
              <p className="text-sm font-semibold leading-relaxed text-[#19171D]">
                {data.reasoning}
              </p>
              <div className="mt-3 flex items-center gap-2 text-xs font-bold text-[#6F6A76]">
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
              <ExplanationSection reasons={reasons} title="Key Matchday Drivers" />
            </motion.div>
          )}

          {/* Signal Tags */}
          {deriveInsights(player).length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.45 }}
              className="rounded-2xl border border-[#E8E3ED] bg-white p-5 shadow-xs"
            >
              <h3 className="mb-3 text-xs font-black uppercase text-[#6F6A76] tracking-wider flex items-center gap-1.5">
                <ShieldCheck size={14} />
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
