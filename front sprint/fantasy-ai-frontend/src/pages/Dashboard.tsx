import { useState } from "react";
import { motion } from "framer-motion";
import { Crown } from "lucide-react";
import { GameweekOverview } from "@/sections/GameweekOverview";
import { AIInsights } from "@/sections/AIInsights";
import { useCaptain, useHealth, useTopPlayers } from "@/hooks/useApi";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { Stat } from "@/components/stats";
import { formatStat } from "@/lib/format";
import { PlayerCard } from "@/components/PlayerCard";
import { PlayerCardSkeleton, ErrorState, EmptyState } from "@/components/states";
import { Drawer } from "@/components/ui/overlays";
import { PlayerDetailPanel } from "@/components/PlayerDetailPanel";
import type { PlayerRecord } from "@/types/api";

export default function Dashboard() {
  const health = useHealth();
  const topPlayers = useTopPlayers(6);
  const captain = useCaptain();
  const [selected, setSelected] = useState<PlayerRecord | null>(null);

  const players = topPlayers.data?.predictions ?? null;
  const gameweek = players?.[0]?.predicted_for_gw;

  return (
    <div className="pb-20">
      <div className="mx-auto max-w-7xl px-5 pt-10 lg:px-8">
        <h1 className="text-3xl font-semibold text-ink">Dashboard</h1>
        <p className="mt-1.5 text-sm text-ink-tertiary">
          Your Fantasy-AI command center for the upcoming Gameweek.
        </p>
      </div>

      <GameweekOverview health={health.data} gameweek={gameweek} />

      {/* Captain pick */}
      <section className="mx-auto max-w-7xl px-5 py-6 lg:px-8">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-ink">
          <Crown size={18} className="text-gold" /> Suggested Captain
        </h2>
        {captain.loading && <PlayerCardSkeleton />}
        {!captain.loading && captain.error && (
          <ErrorState message={captain.error} onRetry={captain.refetch} />
        )}
        {!captain.loading && !captain.error && captain.data && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-col gap-6 rounded-2xl border border-gold/25 bg-gradient-to-br from-gold/[0.06] to-surface p-6 shadow-glow sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="flex items-center gap-4">
              <PlayerAvatar name={captain.data.recommendation.name} size="lg" />
              <div>
                <h3 className="font-display text-xl font-semibold text-ink">
                  {captain.data.recommendation.name ?? "N/A"}
                </h3>
                <TeamBadge team={captain.data.recommendation.team} showName className="mt-1" />
                <p className="mt-2 max-w-md text-xs text-ink-tertiary">{captain.data.reasoning}</p>
              </div>
            </div>
            <div className="flex gap-6">
              <Stat
                label="Expected Points"
                value={formatStat(captain.data.recommendation.predicted_total_points)}
                tone="gold"
                size="lg"
              />
              <Stat label="Pool considered" value={String(captain.data.pool_size)} size="lg" />
            </div>
          </motion.div>
        )}
      </section>

      {/* Top predictions grid */}
      <section className="mx-auto max-w-7xl px-5 py-6 lg:px-8">
        <h2 className="mb-4 text-lg font-semibold text-ink">Top Predictions</h2>
        {topPlayers.loading && (
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <PlayerCardSkeleton key={i} />
            ))}
          </div>
        )}
        {!topPlayers.loading && topPlayers.error && (
          <ErrorState message={topPlayers.error} onRetry={topPlayers.refetch} />
        )}
        {!topPlayers.loading && !topPlayers.error && players && players.length === 0 && (
          <EmptyState title="No predictions available" />
        )}
        {!topPlayers.loading && !topPlayers.error && players && players.length > 0 && (
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {players.map((p) => (
              <PlayerCard key={p.element ?? p.name} player={p} onClick={() => setSelected(p)} />
            ))}
          </div>
        )}
      </section>

      <AIInsights players={players} />

      <Drawer open={selected !== null} onClose={() => setSelected(null)}>
        {selected && <PlayerDetailPanel player={selected} />}
      </Drawer>
    </div>
  );
}
