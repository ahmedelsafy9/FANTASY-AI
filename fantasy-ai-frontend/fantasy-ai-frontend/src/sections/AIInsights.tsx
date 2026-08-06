import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import type { PlayerRecord } from "@/types/api";
import { PlayerAvatar } from "@/components/identity";
import { InsightTag } from "@/components/InsightTag";
import { deriveInsights } from "@/lib/insights";
import { EmptyState } from "@/components/states";

interface AIInsightsProps {
  players: PlayerRecord[] | null;
}

/**
 * Every tag shown here comes from `deriveInsights()`, which only produces a
 * tag when the backing field is actually present on that player's record.
 * If a player has no derivable insights, they're simply skipped from the
 * list — nothing is invented to fill the space.
 */
export function AIInsights({ players }: AIInsightsProps) {
  const withInsights = (players ?? [])
    .map((p) => ({ player: p, insights: deriveInsights(p) }))
    .filter((entry) => entry.insights.length > 0)
    .slice(0, 4);

  return (
    <section className="mx-auto max-w-7xl px-5 py-10 lg:px-8">
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald/10 text-emerald">
          <Sparkles size={17} />
        </div>
        <div>
          <h2 className="font-display text-xl font-bold text-ink sm:text-2xl">AI Insights</h2>
          <p className="mt-0.5 text-sm text-ink-tertiary">
            Signals derived directly from each player's underlying data.
          </p>
        </div>
      </div>

      {withInsights.length === 0 ? (
        <EmptyState
          title="Deeper insights aren't available yet"
          description="Insights are derived from fields like form trend, fixture strength, and recent minutes — none were present in the current dataset for these players."
        />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {withInsights.map(({ player, insights }, i) => (
            <motion.div
              key={player.element ?? player.name ?? i}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.05 }}
              className="rounded-xl border border-border-soft bg-surface p-4"
            >
              <div className="flex items-center gap-2.5">
                <PlayerAvatar name={player.name} photoUrl={player.photo_url} size="md" />
                <div className="min-w-0">
                  <span className="block truncate text-sm font-semibold text-ink">
                    {player.name ?? "N/A"}
                  </span>
                  {player.team && (
                    <span className="text-xs text-ink-tertiary">{player.team}</span>
                  )}
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {insights.map((insight) => (
                  <InsightTag key={insight.label} insight={insight} />
                ))}
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </section>
  );
}
