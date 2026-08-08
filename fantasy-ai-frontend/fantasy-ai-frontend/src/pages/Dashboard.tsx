import { useState } from "react";
import { motion } from "framer-motion";
import { Crown, BarChart3, ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import { GameweekOverview } from "@/sections/GameweekOverview";
import { AIInsights } from "@/sections/AIInsights";
import { useCaptain, useHealth, useTopPlayers } from "@/hooks/useApi";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { PredictionScore } from "@/components/PredictionScore";
import { FixtureBadge } from "@/components/FixtureBadge";
import { PlayerCard } from "@/components/PlayerCard";
import { PlayerCardSkeleton, ErrorState, EmptyState } from "@/components/states";
import { Drawer } from "@/components/ui/overlays";
import { PlayerDetailPanel } from "@/components/PlayerDetailPanel";
import { Button } from "@/components/ui/primitives";
import type { PlayerRecord } from "@/types/api";

export default function Dashboard() {
  const health = useHealth();
  const topPlayers = useTopPlayers(6);
  const captain = useCaptain();
  const [selected, setSelected] = useState<PlayerRecord | null>(null);

  const players = topPlayers.data?.predictions ?? null;
  const gameweek = players?.[0]?.predicted_for_gw;

  return (
    <div className="pb-safe-bottom">
      <div className="mx-auto max-w-7xl px-4 pt-8 lg:px-8">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0] shadow-sm">
            <BarChart3 size={20} />
          </div>
          <div>
            <h1 className="font-display text-2xl font-black text-[#0F172A] sm:text-3xl">Manager Dashboard</h1>
            <p className="text-sm font-semibold text-[#475569]">
              Your Fantasy-AI command center for the upcoming Gameweek.
            </p>
          </div>
        </div>
      </div>

      <GameweekOverview health={health.data} gameweek={gameweek} />

      {/* Suggested Captain */}
      <section className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="flex items-center gap-2 font-display text-xl font-black text-[#0F172A]">
            <Crown size={20} className="text-[#92400E]" /> Suggested Captain Pick
          </h2>
          <Link to="/captain">
            <Button variant="secondary" size="sm" className="gap-1.5 font-bold">
              <span>Full Details</span>
              <ArrowRight size={14} />
            </Button>
          </Link>
        </div>

        {captain.loading && <PlayerCardSkeleton />}

        {!captain.loading && captain.error && (
          <ErrorState message={captain.error} onRetry={captain.refetch} />
        )}

        {!captain.loading && !captain.error && captain.data && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-col gap-4 rounded-chunky-lg border border-[#FDE68A] bg-gradient-to-r from-[#FFFBEB] via-white to-white p-6 sm:flex-row sm:items-center sm:justify-between shadow-card"
          >
            <div className="flex items-center gap-4">
              <PlayerAvatar
                name={captain.data.recommendation.name}
                photoUrl={captain.data.recommendation.photo_url}
                size="lg"
                className="ring-4 ring-[#F59E0B] shadow-sm"
              />
              <div>
                <h3 className="font-display text-xl font-black text-[#0F172A]">
                  {captain.data.recommendation.name ?? "N/A"}
                </h3>
                <TeamBadge
                  team={captain.data.recommendation.team}
                  logoUrl={captain.data.recommendation.team_logo_url}
                  showName
                  className="mt-1"
                />
                <p className="mt-2 max-w-md text-xs font-semibold text-[#475569]">
                  {captain.data.reasoning}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-6">
              <PredictionScore points={captain.data.recommendation.predicted_total_points} size="lg" />
              <FixtureBadge player={captain.data.recommendation} size="md" />
            </div>
          </motion.div>
        )}
      </section>

      {/* Top predictions grid */}
      <section className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
        <h2 className="mb-4 font-display text-xl font-black text-[#0F172A]">Top Gameweek Predictions</h2>
        {topPlayers.loading && (
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
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
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
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
