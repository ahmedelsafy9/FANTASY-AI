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

export function AIInsights({ players }: AIInsightsProps) {
  const withInsights = (players ?? [])
    .map((p) => ({ player: p, insights: deriveInsights(p) }))
    .filter((entry) => entry.insights.length > 0)
    .slice(0, 4);

  return (
    <section className="mx-auto max-w-7xl px-4 py-8 lg:px-8">
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#ECFDF5] text-[#059669]">
          <Sparkles size={18} />
        </div>
        <div>
          <h2 className="font-display text-xl font-black text-[#0F172A] sm:text-2xl">Player AI Signals</h2>
          <p className="mt-0.5 text-sm font-semibold text-[#64748B]">
            Signals derived directly from underlying model metrics.
          </p>
        </div>
      </div>

      {withInsights.length === 0 ? (
        <EmptyState
          title="Deeper insights aren't available yet"
          description="Insights are derived from form trends, fixture strength, and recent minutes."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {withInsights.map(({ player, insights }, i) => (
            <motion.div
              key={player.element ?? player.name ?? i}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.05 }}
              className="rounded-chunky-lg border border-[#E2E8F0] bg-white p-4 shadow-card"
            >
              <div className="flex items-center gap-3">
                <PlayerAvatar name={player.name} photoUrl={player.photo_url} size="md" />
                <div className="min-w-0">
                  <span className="block truncate text-sm font-black text-[#0F172A]">
                    {player.name ?? "N/A"}
                  </span>
                  {player.team && (
                    <span className="text-xs font-semibold text-[#64748B]">{player.team}</span>
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
