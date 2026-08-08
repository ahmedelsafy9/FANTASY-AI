import { motion } from "framer-motion";
import { Crown, Sparkles, Users } from "lucide-react";
import { useCaptain } from "@/hooks/useApi";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { FixtureBadge } from "@/components/FixtureBadge";
import { PredictionScore } from "@/components/PredictionScore";
import { InsightTag } from "@/components/InsightTag";
import { PlayerCardSkeleton, ErrorState, EmptyState } from "@/components/states";
import { deriveInsights } from "@/lib/insights";

export default function Captain() {
  const { data, loading, error, refetch } = useCaptain();

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 pb-safe-bottom lg:px-8">
      {/* Header */}
      <div className="mb-8 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#FFFBEB] text-[#92400E] border border-[#FDE68A] shadow-sm">
          <Crown size={20} />
        </div>
        <div>
          <h1 className="font-display text-2xl font-black text-[#0F172A] sm:text-3xl">
            AI Captain Recommendation
          </h1>
          <p className="text-sm font-semibold text-[#475569]">
            Top recommended captain choice for maximum 2× points boost.
          </p>
        </div>
      </div>

      {loading && (
        <div className="max-w-md">
          <PlayerCardSkeleton />
        </div>
      )}

      {!loading && error && <ErrorState message={error} onRetry={refetch} />}

      {!loading && !error && !data && (
        <EmptyState
          title="No captain recommendation available"
          description="Run the prediction pipeline to generate a captain pick."
        />
      )}

      {!loading && !error && data && (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="flex flex-col gap-6"
        >
          {/* Captain hero card */}
          <div className="relative overflow-hidden rounded-chunky-xl border border-[#FDE68A] bg-gradient-to-br from-[#FFFBEB] via-white to-[#ECFDF5] shadow-card">
            {/* Top gold stripe */}
            <div className="h-1.5 w-full bg-gradient-to-r from-[#F59E0B] via-[#FBBF24] to-[#10B981]" />

            <div className="flex flex-col items-center gap-6 p-8 text-center sm:p-10">
              {/* Crown icon */}
              <motion.div
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ duration: 0.4, delay: 0.1 }}
                className="flex h-16 w-16 items-center justify-center rounded-2xl bg-[#F59E0B] text-[#0F172A] shadow-btn-raised border-2 border-white animate-bounce-sm"
              >
                <Crown size={32} />
              </motion.div>

              {/* Player photo */}
              <motion.div
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ duration: 0.4, delay: 0.15 }}
              >
                <PlayerAvatar
                  name={data.recommendation.name}
                  photoUrl={data.recommendation.photo_url}
                  size="xl"
                  className="ring-4 ring-[#F59E0B] shadow-card"
                />
              </motion.div>

              {/* Name + team */}
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.2 }}
              >
                <h2 className="font-display text-3xl font-black text-[#0F172A] sm:text-4xl">
                  {data.recommendation.name ?? "N/A"}
                </h2>
                <div className="mt-2 flex items-center justify-center gap-2">
                  <TeamBadge
                    team={data.recommendation.team}
                    logoUrl={data.recommendation.team_logo_url}
                    size="md"
                    showName
                  />
                  {data.recommendation.position && (
                    <span className="rounded-full bg-[#0F172A] px-3 py-0.5 text-xs font-black uppercase text-white shadow-sm">
                      {data.recommendation.position}
                    </span>
                  )}
                </div>
              </motion.div>

              {/* Predicted points */}
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.5, delay: 0.25 }}
              >
                <PredictionScore
                  points={data.recommendation.predicted_total_points}
                  size="xl"
                  className="items-center"
                />
              </motion.div>

              {/* Fixture */}
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.3 }}
              >
                <FixtureBadge player={data.recommendation} size="lg" />
              </motion.div>
            </div>
          </div>

          {/* AI Reasoning */}
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.35 }}
            className="rounded-chunky-lg border border-[#A7F3D0] bg-[#ECFDF5] p-5 shadow-sm"
          >
            <h3 className="mb-2 flex items-center gap-2 text-xs font-black uppercase text-[#059669]">
              <Sparkles size={14} />
              AI Selection Reasoning
            </h3>
            <p className="text-sm font-semibold leading-relaxed text-[#334155]">
              {data.reasoning}
            </p>
            <div className="mt-3 flex items-center gap-2 text-xs font-extrabold text-[#64748B]">
              <Users size={14} />
              <span>{data.pool_size} total players evaluated</span>
            </div>
          </motion.div>

          {/* Insights */}
          {deriveInsights(data.recommendation).length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.4 }}
            >
              <h3 className="mb-3 text-xs font-black uppercase text-[#64748B]">
                Player Insights
              </h3>
              <div className="flex flex-wrap gap-2">
                {deriveInsights(data.recommendation).map((insight) => (
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
