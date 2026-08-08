import { useMemo } from "react";
import { usePredictions } from "@/hooks/useApi";
import { TeamBadge } from "@/components/identity";
import { UpcomingFixtures } from "@/components/UpcomingFixtures";
import { PlayerCardSkeleton, ErrorState, EmptyState } from "@/components/states";
import type { UpcomingFixture } from "@/types/api";

export function FixtureIntelligence() {
  const { data, loading, error, refetch } = usePredictions();

  const teamFixturesMap = useMemo(() => {
    if (!data?.predictions)
      return new Map<string, { team: string; logoUrl?: string | null; fixtures: UpcomingFixture[] }>();

    const map = new Map<string, { team: string; logoUrl?: string | null; fixtures: UpcomingFixture[] }>();
    for (const player of data.predictions) {
      if (
        player.team &&
        player.upcoming_fixtures &&
        player.upcoming_fixtures.length > 0 &&
        !map.has(player.team)
      ) {
        map.set(player.team, {
          team: player.team,
          logoUrl: player.team_logo_url,
          fixtures: player.upcoming_fixtures,
        });
      }
    }
    return map;
  }, [data]);

  const teamCards = useMemo(() => {
    return Array.from(teamFixturesMap.values()).sort((a, b) => a.team.localeCompare(b.team));
  }, [teamFixturesMap]);

  return (
    <section className="mx-auto max-w-7xl px-4 py-8 lg:px-8">
      <div className="mb-6">
        <h2 className="text-2xl font-black text-navy sm:text-3xl">Fixture Intelligence</h2>
        <p className="mt-1 max-w-xl text-sm font-semibold text-slate-500">
          Upcoming match sequences, home/away difficulty, and FDR ratings for Premier League teams.
        </p>
      </div>

      {loading && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <PlayerCardSkeleton key={i} />
          ))}
        </div>
      )}

      {!loading && error && <ErrorState message={error} onRetry={refetch} />}

      {!loading && !error && teamCards.length === 0 && (
        <EmptyState
          title="No fixture data available"
          description="The live FPL API fixture metadata could not be loaded."
        />
      )}

      {!loading && !error && teamCards.length > 0 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {teamCards.map(({ team, logoUrl, fixtures }) => (
            <div
              key={team}
              className="flex flex-col gap-3 rounded-chunky-lg border border-slate-200 bg-white p-5 shadow-card transition-all hover:border-emerald/40"
            >
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <TeamBadge team={team} logoUrl={logoUrl} size="md" showName />
                <span className="text-xs font-bold text-slate-500">
                  Next {fixtures.length} Matches
                </span>
              </div>
              <UpcomingFixtures fixtures={fixtures} variant="full" maxFixtures={5} />
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
