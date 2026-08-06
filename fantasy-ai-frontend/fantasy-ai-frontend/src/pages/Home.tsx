import { useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight, Crown } from "lucide-react";
import { Hero } from "@/sections/Hero";
import { GameweekOverview } from "@/sections/GameweekOverview";
import { TopPredictions } from "@/sections/TopPredictions";
import { AIInsights } from "@/sections/AIInsights";
import { HowItWorks } from "@/sections/HowItWorks";
import { useCaptain, useHealth, useTopPlayers } from "@/hooks/useApi";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { PredictionScore } from "@/components/PredictionScore";
import { FixtureBadge } from "@/components/FixtureBadge";
import { Button } from "@/components/ui/primitives";
import { PlayerCardSkeleton, ErrorState } from "@/components/states";
import type { PlayerRecord } from "@/types/api";
import { Drawer } from "@/components/ui/overlays";
import { PlayerDetailPanel } from "@/components/PlayerDetailPanel";

export default function Home() {
  const health = useHealth();
  const topPlayers = useTopPlayers(10);
  const captain = useCaptain();
  const [selected, setSelected] = useState<PlayerRecord | null>(null);

  const players = topPlayers.data?.predictions ?? null;
  const spotlightPlayer = players && players.length > 0 ? players[0] : null;
  const gameweek = spotlightPlayer?.predicted_for_gw;

  return (
    <div className="pb-safe-bottom">
      <Hero gameweek={gameweek} modelName={health.data?.model_name} />
      <GameweekOverview health={health.data} gameweek={gameweek} />

      {/* Captain pick highlight */}
      <section className="mx-auto max-w-7xl px-5 py-8 lg:px-8">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="flex items-center gap-2 font-display text-lg font-bold text-ink">
            <Crown size={18} className="text-gold" />
            AI Captain Pick
          </h2>
          <Link to="/captain">
            <Button variant="ghost" size="sm">
              Full details <ArrowRight size={14} />
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
            className="flex flex-col gap-4 rounded-xl border border-gold/20 bg-gradient-to-r from-gold/[0.05] via-surface to-surface p-5 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="flex items-center gap-4">
              <PlayerAvatar
                name={captain.data.recommendation.name}
                photoUrl={captain.data.recommendation.photo_url}
                size="lg"
                className="ring-2 ring-gold/25"
              />
              <div>
                <h3 className="font-display text-lg font-bold text-ink">
                  {captain.data.recommendation.name ?? "N/A"}
                </h3>
                <div className="mt-1 flex items-center gap-2">
                  <TeamBadge
                    team={captain.data.recommendation.team}
                    logoUrl={captain.data.recommendation.team_logo_url}
                    showName
                    size="sm"
                  />
                </div>
                <p className="mt-2 max-w-md text-xs text-ink-tertiary">
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

      {/* Top predictions */}
      <TopPredictions
        players={players}
        loading={topPlayers.loading}
        error={topPlayers.error}
        onRetry={topPlayers.refetch}
        onSelect={setSelected}
      />

      <AIInsights players={players} />
      <HowItWorks />

      <Drawer open={selected !== null} onClose={() => setSelected(null)}>
        {selected && <PlayerDetailPanel player={selected} />}
      </Drawer>
    </div>
  );
}
