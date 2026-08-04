import { useState } from "react";
import { Hero } from "@/sections/Hero";
import { GameweekOverview } from "@/sections/GameweekOverview";
import { TopPredictions } from "@/sections/TopPredictions";
import { FixtureIntelligence } from "@/sections/FixtureIntelligence";
import { PlayerSpotlight } from "@/sections/PlayerSpotlight";
import { AIInsights } from "@/sections/AIInsights";
import { HowItWorks } from "@/sections/HowItWorks";
import { useHealth, useTopPlayers } from "@/hooks/useApi";
import type { PlayerRecord } from "@/types/api";
import { Drawer } from "@/components/ui/overlays";
import { PlayerDetailPanel } from "@/components/PlayerDetailPanel";

export default function Home() {
  const health = useHealth();
  const topPlayers = useTopPlayers(10);
  const [selected, setSelected] = useState<PlayerRecord | null>(null);

  const players = topPlayers.data?.predictions ?? null;
  const spotlightPlayer = players && players.length > 0 ? players[0] : null;
  const gameweek = spotlightPlayer?.predicted_for_gw;

  return (
    <>
      <Hero gameweek={gameweek} modelName={health.data?.model_name} />
      <GameweekOverview health={health.data} gameweek={gameweek} />
      <TopPredictions
        players={players}
        loading={topPlayers.loading}
        error={topPlayers.error}
        onRetry={topPlayers.refetch}
        onSelect={setSelected}
      />
      <FixtureIntelligence />
      <PlayerSpotlight player={spotlightPlayer} />
      <AIInsights players={players} />
      <HowItWorks />

      <Drawer open={selected !== null} onClose={() => setSelected(null)}>
        {selected && <PlayerDetailPanel player={selected} />}
      </Drawer>
    </>
  );
}
