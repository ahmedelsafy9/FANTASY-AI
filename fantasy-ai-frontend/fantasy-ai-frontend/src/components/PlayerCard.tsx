import { Link } from "react-router-dom";
import type { PlayerRecord } from "@/types/api";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { UpcomingFixtures } from "@/components/UpcomingFixtures";
import { ExpectedPoints } from "@/components/ExpectedPoints";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { deriveConfidenceLevel, deriveReasons, deriveRecommendation } from "@/lib/insights";
import { getPlayerPrice } from "@/hooks/useSquad";
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
        "relative flex flex-col overflow-hidden border border-[#E2E8F0] bg-white text-[#0F172A] p-0 shadow-card transition-all duration-200 hover:border-[#10B981] hover:shadow-card-playful",
        className,
      )}
      onClick={onClick}
    >
      {/* Top Header Bar */}
      <div className="flex items-center justify-between border-b border-[#E2E8F0] bg-[#F8FAFC] px-4 py-2.5">
        <div className="flex items-center gap-2">
          {typeof rank === "number" && (
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#F59E0B] border border-[#D97706] font-mono text-xs font-black text-[#0F172A] shadow-sm">
              #{rank}
            </span>
          )}
          <TeamBadge team={player.team} logoUrl={player.team_logo_url} size="sm" showName />
        </div>

        <div className="flex items-center gap-2">
          {player.position && (
            <span className="rounded-full bg-[#F1F5F9] border border-[#CBD5E1] px-2.5 py-0.5 text-[10px] font-black uppercase text-[#334155]">
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
            className="ring-2 ring-[#10B981] shadow-sm"
          />
          <div className="min-w-0 flex-1">
            <h3 className="font-display text-base font-black text-[#0F172A] truncate">
              {player.name ?? "N/A"}
            </h3>
            <div className="mt-1 flex items-center gap-2">
              <span className="numeral text-xs font-black text-[#059669] bg-[#ECFDF5] px-2 py-0.5 rounded border border-[#A7F3D0]">
                £{price.toFixed(1)}m
              </span>
              <span className="text-[10px] font-bold text-[#64748B]">
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
      <div className="border-t border-[#E2E8F0] bg-[#F8FAFC] px-4 py-2.5">
        <UpcomingFixtures player={player} variant="compact" maxFixtures={3} />
      </div>

      {/* Key Reason Strip */}
      {topReason && (
        <div className="border-t border-[#E2E8F0] bg-white px-4 py-2.5">
          <div className="flex items-center gap-2 text-xs font-semibold text-[#475569]">
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
