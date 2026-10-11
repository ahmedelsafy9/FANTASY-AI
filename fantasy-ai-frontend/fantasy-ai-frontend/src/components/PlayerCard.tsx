import { Link } from "react-router-dom";
import { ChevronRight, Sparkles } from "lucide-react";
import type { PlayerRecord, UpcomingFixture } from "@/types/api";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { PlayerAvailabilityBadge } from "@/components/PlayerAvailabilityBadge";
import { ExpectedPoints } from "@/components/ExpectedPoints";
import { FDRBadge } from "@/components/FDRBadge";
import { getPlayerPrice } from "@/hooks/useSquad";
import { getTeamCode } from "@/lib/format";
import { cn } from "@/lib/utils";

interface PlayerCardProps {
  player: PlayerRecord;
  rank?: number;
  onClick?: () => void;
  className?: string;
  /** If true, the card links directly to the player detail page */
  linkToDetail?: boolean;
}

/**
 * Fantasy Wizard Decision-Oriented Player Card.
 *
 * Prioritizes what matters for instant FPL decisions:
 * 1. Player Portrait & Name
 * 2. Club Identity & Position
 * 3. Predicted Points (whole number visual focal point)
 * 4. Official Availability Status Badge
 * 5. Next Fixture & Opponent
 * 6. Price & Key Decision Metric
 */
export function PlayerCard({
  player,
  rank,
  onClick,
  className,
  linkToDetail = false,
}: PlayerCardProps) {
  const price = getPlayerPrice(player);
  const xPts = player.predicted_expected_points ?? player.predicted_total_points;
  const isElite = typeof xPts === "number" && Math.round(xPts) >= 7;

  const playerId = player.element !== undefined ? String(player.element) : player.name ?? "";

  // Extract next fixture
  const nextFixture: UpcomingFixture | null =
    player.upcoming_fixtures && player.upcoming_fixtures.length > 0
      ? player.upcoming_fixtures[0]
      : player.opponent_team
      ? {
          is_home: player.is_home === 1,
          opponent_team_id: 0,
          opponent_name: player.opponent_team,
          opponent_short_name: getTeamCode(player.opponent_team),
          opponent_logo_url: player.opponent_logo_url,
          difficulty: player.fixture_difficulty,
        }
      : null;

  const cardContent = (
    <article
      className={cn(
        "group relative flex flex-col justify-between overflow-hidden rounded-2xl border bg-ivory-surface text-ink-primary shadow-card transition-all duration-300",
        "hover:-translate-y-1 hover:shadow-card-hover",
        isElite
          ? "border-gold-border/70 hover:border-gold-metallic"
          : "border-border hover:border-stadium-forest/60",
        (onClick || linkToDetail) && "cursor-pointer",
        className,
      )}
      onClick={onClick}
    >
      {/* Top Accent Rim */}
      <div
        className={cn(
          "h-1 w-full transition-colors",
          isElite
            ? "bg-gradient-to-r from-gold-metallic via-gold-bright to-gold-muted"
            : "bg-gradient-to-r from-stadium-deep via-stadium-forest to-stadium-deep",
        )}
      />

      <div className="p-4 sm:p-5 flex flex-col gap-4">
        {/* Header Bar: Rank / Club / Position / Availability */}
        <div className="flex items-center justify-between gap-2 border-b border-border/60 pb-3">
          <div className="flex items-center gap-2 min-w-0">
            {typeof rank === "number" && (
              <span
                className={cn(
                  "flex h-6 w-6 shrink-0 items-center justify-center rounded-full font-mono text-[11px] font-black border shadow-xs",
                  rank <= 3
                    ? "bg-gold-light border-gold-border text-gold-dark"
                    : "bg-stadium-surface/10 border-border text-stadium-deep",
                )}
                title={`Rank #${rank}`}
              >
                {rank}
              </span>
            )}
            <TeamBadge team={player.team} logoUrl={player.team_logo_url} size="sm" showName />
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            {player.position && (
              <span className="rounded-md bg-ivory-subtle border border-border px-2 py-0.5 font-mono text-[10px] font-black uppercase text-ink-primary">
                {player.position === "GKP" ? "GK" : player.position}
              </span>
            )}
            <PlayerAvailabilityBadge player={player} size="sm" />
          </div>
        </div>

        {/* Main Body: Player Avatar + Name + Price + Predicted Points Focal Area */}
        <div className="flex items-center justify-between gap-3">
          {/* Player Identity */}
          <div className="flex items-center gap-3.5 min-w-0 flex-1">
            <div className="relative shrink-0">
              <PlayerAvatar
                name={player.name}
                photoUrl={player.photo_url}
                size="lg"
                className={cn(
                  "ring-2 transition-transform group-hover:scale-105",
                  isElite ? "ring-gold-metallic/50" : "ring-border",
                )}
              />
              {isElite && (
                <div
                  className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-gold-metallic text-stadium-dark shadow-xs"
                  title="Elite Gameweek Projection"
                >
                  <Sparkles size={9} className="fill-stadium-dark" />
                </div>
              )}
            </div>

            <div className="min-w-0 flex-1">
              <h3 className="font-display text-base sm:text-lg font-black tracking-tight text-ink-primary truncate group-hover:text-stadium-forest transition-colors">
                {player.name ?? "Unknown Player"}
              </h3>
              <div className="mt-1 flex items-center gap-2 flex-wrap">
                <span className="numeral text-xs font-black text-ink-primary bg-ivory-subtle px-2 py-0.5 rounded border border-border">
                  £{price.toFixed(1)}m
                </span>
                {player.selected_by_percent !== undefined && player.selected_by_percent !== null && (
                  <span className="text-[11px] font-semibold text-ink-secondary">
                    {typeof player.selected_by_percent === "number"
                      ? `${player.selected_by_percent}% owned`
                      : `${player.selected_by_percent}% owned`}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Predicted Points Visual Focal Point */}
          <div className="shrink-0 pl-2">
            <ExpectedPoints points={xPts} size="md" showLabel={true} />
          </div>
        </div>

        {/* Fixture Strip */}
        <div className="mt-0.5 rounded-xl bg-ivory-subtle/80 border border-border/80 px-3 py-2 flex items-center justify-between">
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-[10px] font-bold uppercase tracking-wider text-ink-secondary">
              Next Match:
            </span>
            {nextFixture ? (
              <div className="flex items-center gap-1.5 min-w-0">
                <TeamBadge
                  team={nextFixture.opponent_name}
                  logoUrl={nextFixture.opponent_logo_url}
                  size="sm"
                />
                <span className="font-display text-xs font-black text-ink-primary truncate">
                  {nextFixture.opponent_short_name || getTeamCode(nextFixture.opponent_name)}
                </span>
                <span
                  className={cn(
                    "font-mono text-[10px] font-black px-1.5 py-0.2 rounded",
                    nextFixture.is_home
                      ? "bg-stadium-deep text-ivory-surface"
                      : "bg-border text-ink-secondary",
                  )}
                >
                  {nextFixture.is_home ? "H" : "A"}
                </span>
                <FDRBadge difficulty={nextFixture.difficulty} size="sm" />
              </div>
            ) : (
              <span className="text-xs font-medium text-ink-secondary italic">
                Schedule pending
              </span>
            )}
          </div>

          <ChevronRight
            size={16}
            className="text-ink-secondary shrink-0 transition-transform group-hover:translate-x-1 group-hover:text-gold-metallic"
          />
        </div>
      </div>
    </article>
  );

  if (linkToDetail) {
    return (
      <Link
        to={`/players/${encodeURIComponent(playerId)}`}
        className="block focus:outline-none focus-visible:ring-2 focus-visible:ring-gold-metallic rounded-2xl"
      >
        {cardContent}
      </Link>
    );
  }

  return cardContent;
}
