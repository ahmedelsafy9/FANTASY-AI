import { motion } from "framer-motion";
import { Crown, Sparkles, Users } from "lucide-react";
import { useCaptain } from "@/hooks/useApi";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { FixtureBadge } from "@/components/FixtureBadge";
import { PredictionScore } from "@/components/PredictionScore";
import { InsightTag } from "@/components/InsightTag";
import { PlayerCardSkeleton, ErrorState, EmptyState } from "@/components/states";
import { deriveInsights } from "@/lib/insights";

/**
 * Dedicated Captain Pick page — uses the existing useCaptain() hook
 * which maps to GET /captain. Displays the AI recommendation with
 * maximum visual prominence. All data from the backend; nothing fabricated.
 */
export default function Captain() {
  const { data, loading, error, refetch } = useCaptain();

  return (
    <div className="mx-auto max-w-3xl px-5 py-8 pb-safe-bottom lg:px-8">
      {/* Header */}
      <div className="mb-8 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gold/10 text-gold">
          <Crown size={20} />
        </div>
        <div>
          <h1 className="font-display text-2xl font-bold text-ink sm:text-3xl">
            Captain Pick
          </h1>
          <p className="text-sm text-ink-tertiary">
            AI-recommended captain for maximum points.
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
          <div className="relative overflow-hidden rounded-2xl border border-gold/20 bg-gradient-to-br from-gold/[0.06] via-surface to-pitch-dark/30">
            {/* Gold accent */}
            <div className="h-1 w-full bg-gradient-to-r from-gold via-gold/60 to-transparent" />

            <div className="flex flex-col items-center gap-6 p-8 text-center sm:p-10">
              {/* Crown icon */}
              <motion.div
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ duration: 0.4, delay: 0.1 }}
                className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gold/15 text-gold shadow-glow"
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
                  name={data.recommendation.name}
                  photoUrl={data.recommendation.photo_url}
                  size="xl"
                  className="ring-4 ring-gold/25"
                />
              </motion.div>

              {/* Name + team */}
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: 0.2 }}
              >
                <h2 className="font-display text-2xl font-bold text-ink sm:text-3xl">
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
                    <span className="rounded bg-white/10 px-2 py-0.5 text-xs font-semibold uppercase text-ink-secondary">
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
            className="rounded-xl border border-emerald/15 bg-emerald/[0.04] p-5"
          >
            <h3 className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-emerald">
              <Sparkles size={13} />
              AI Reasoning
            </h3>
            <p className="text-sm leading-relaxed text-ink-secondary">
              {data.reasoning}
            </p>
            <div className="mt-3 flex items-center gap-2 text-xs text-ink-tertiary">
              <Users size={13} />
              <span>{data.pool_size} players evaluated</span>
            </div>
          </motion.div>

          {/* Insights */}
          {deriveInsights(data.recommendation).length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.4 }}
            >
              <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-ink-tertiary">
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
