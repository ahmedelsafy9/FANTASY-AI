import { Link } from "react-router-dom";
import type { PlayerRecord } from "@/types/api";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { UpcomingFixtures } from "@/components/UpcomingFixtures";
import { ExpectedPoints } from "@/components/ExpectedPoints";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { deriveConfidenceLevel, deriveReasons, deriveRecommendation } from "@/lib/insights";
import { getPlayerPrice } from "@/hooks/useSquad";
import { LowOwnershipBadge } from "@/components/LowOwnershipBadge";
import { Card } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

interface PlayerCardProps {
  player: PlayerRecord;
  rank?: number;
  onClick?: () => void;
  className?: string;
  /** If true, the card links to the player detail page */
  linkToDetail?: boolean;
}

/**
 * ONE reusable player card used consistently everywhere.
 *
 * Shows: Player identity → Expected points (prominent) → Confidence →
 *        Next opponent → Top reason → Price
 *
 * Does NOT show: raw ML probabilities, rank scores, P85, P(≥6) etc.
 */
export function PlayerCard({
  player,
  rank,
  onClick,
  className,
  linkToDetail = false,
}: PlayerCardProps) {
  const confidence = deriveConfidenceLevel(player);
  const reasons = deriveReasons(player);
  const recommendation = deriveRecommendation(player, confidence);
  const price = getPlayerPrice(player);
  const xPts = player.predicted_expected_points ?? player.predicted_total_points;
  const topReason = reasons[0];

  const playerId = player.element !== undefined ? String(player.element) : player.name ?? "";

  const cardContent = (
    <Card
      interactive={!!onClick || linkToDetail}
      as="article"
      className={cn(
        "relative flex flex-col overflow-hidden border border-[#E8E3ED] bg-white text-[#19171D] p-0 shadow-sm transition-all duration-200 hover:border-[#7041C5] hover:shadow-md",
        className,
      )}
      onClick={onClick}
    >
      {/* Top Header Bar */}
      <div className="flex items-center justify-between border-b border-[#E8E3ED] bg-[#F8F7FA] px-4 py-2.5">
        <div className="flex items-center gap-2">
          {typeof rank === "number" && (
            <span
              className={cn(
                "flex h-6 w-6 items-center justify-center rounded-full font-mono text-xs font-black shadow-sm border",
                rank <= 3
                  ? "bg-[#FDF8EC] border-[#E5D08E] text-[#8C680E]"
                  : "bg-[#EEE7FA] border-[#D4C3ED] text-[#452477]",
              )}
            >
              #{rank}
            </span>
          )}
          <TeamBadge team={player.team} logoUrl={player.team_logo_url} size="sm" showName />
        </div>

        <div className="flex items-center gap-2">
          {player.position && (
            <span className="rounded-full bg-[#EEE7FA] border border-[#D4C3ED] px-2.5 py-0.5 text-[10px] font-black uppercase text-[#452477]">
              {player.position === "GKP" ? "GK" : player.position}
            </span>
          )}
          <ConfidenceBadge level={confidence} showTooltip={false} />
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex items-center justify-between gap-3 p-4">
        {/* Avatar + Name + Price */}
        <div className="flex items-center gap-3.5 min-w-0">
          <PlayerAvatar
            name={player.name}
            photoUrl={player.photo_url}
            size="lg"
            className="ring-2 ring-[#7041C5]/20 shadow-sm"
          />
          <div className="min-w-0 flex-1">
            <h3 className="font-display text-base font-black text-[#19171D] truncate">
              {player.name ?? "N/A"}
            </h3>
            <div className="mt-1 flex items-center gap-2 flex-wrap">
              <span className="numeral text-xs font-black text-[#19171D] bg-[#F4F3F6] px-2 py-0.5 rounded border border-[#E8E3ED]">
                £{price.toFixed(1)}m
              </span>
              <LowOwnershipBadge
                ownership={player.selected_by_percent ?? (player as Record<string, unknown>).ownership_pct as number | undefined}
                predictedPoints={xPts}
              />
              <span className="text-[10px] font-bold text-[#6F6A76]">
                {recommendation}
              </span>
            </div>
          </div>
        </div>

        {/* Expected Points (Prominent Feature) */}
        <div className="shrink-0">
          <ExpectedPoints points={xPts} size="md" showLabel={true} />
        </div>
      </div>

      {/* Upcoming Fixtures */}
      <div className="border-t border-[#E8E3ED] bg-[#F8F7FA] px-4 py-2.5">
        <UpcomingFixtures player={player} variant="compact" maxFixtures={3} />
      </div>

      {/* Key Reason Strip */}
      {topReason && (
        <div className="border-t border-[#E8E3ED] bg-white px-4 py-2.5">
          <div className="flex items-center gap-2 text-xs font-semibold text-[#6F6A76]">
            <span className="text-sm leading-none">{topReason.icon}</span>
            <span>{topReason.text}</span>
          </div>
        </div>
      )}
    </Card>
  );

  if (linkToDetail) {
    return (
      <Link to={`/players/${encodeURIComponent(playerId)}`} className="block">
        {cardContent}
      </Link>
    );
  }

  return cardContent;
}
