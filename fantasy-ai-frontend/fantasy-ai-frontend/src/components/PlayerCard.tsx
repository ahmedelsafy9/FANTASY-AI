import type { PlayerRecord } from "@/types/api";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { UpcomingFixtures } from "@/components/UpcomingFixtures";
import { formatStat } from "@/lib/format";
import { deriveInsights, derivePlayingTimeReliability } from "@/lib/insights";
import { getPlayerPrice } from "@/hooks/useSquad";
import { Card } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

interface PlayerCardProps {
  player: PlayerRecord;
  rank?: number;
  onClick?: () => void;
  className?: string;
}

export function PlayerCard({ player, rank, onClick, className }: PlayerCardProps) {
  const insights = deriveInsights(player);
  const reliability = derivePlayingTimeReliability(player);
  const price = getPlayerPrice(player);

  const topInsight = insights.find((i) => i.tone === "teal" || i.tone === "gold") ?? insights[0];

  return (
    <Card
      interactive={!!onClick}
      as="article"
      className={cn(
        "relative flex flex-col overflow-hidden border border-[#E2E8F0] bg-white text-[#0F172A] p-0 shadow-card transition-all duration-200 hover:border-[#10B981] hover:shadow-card-playful",
        className,
      )}
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

        {player.position && (
          <span className="rounded-full bg-[#F1F5F9] border border-[#CBD5E1] px-2.5 py-0.5 text-[10px] font-black uppercase text-[#334155]">
            {player.position === "GKP" ? "GK" : player.position}
          </span>
        )}
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
              {topInsight && (
                <span className="rounded-md bg-[#F1F5F9] border border-[#CBD5E1] px-1.5 py-0.5 text-[10px] font-black text-[#334155]">
                  {topInsight.label}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Model Predicted Points Box (Prominent Feature) */}
        <div className="flex flex-col items-end shrink-0 rounded-2xl border-2 border-[#FDE68A] bg-[#FFFBEB] p-2.5 text-right shadow-sm">
          <span className="text-[9px] font-black uppercase tracking-wider text-[#92400E]">
            AI xPts
          </span>
          <span className="numeral text-2xl font-black text-[#92400E] leading-none">
            {formatStat(player.predicted_total_points)}
          </span>
        </div>
      </div>

      {/* Upcoming Fixtures */}
      <div className="border-t border-[#E2E8F0] bg-[#F8FAFC] px-4 py-2.5">
        <UpcomingFixtures player={player} variant="compact" maxFixtures={3} />
      </div>

      {/* Quick Stats Strip */}
      <div className="grid grid-cols-3 divide-x divide-[#E2E8F0] border-t border-[#E2E8F0] bg-white text-center">
        <div className="py-2.5">
          <span className="block text-[9px] font-black uppercase tracking-wider text-[#64748B]">
            Form (3GW)
          </span>
          <span className="numeral text-xs font-black text-[#0F172A]">
            {formatStat(player.total_points_avg_last_3)}
          </span>
        </div>
        <div className="py-2.5">
          <span className="block text-[9px] font-black uppercase tracking-wider text-[#64748B]">
            Mins (5GW)
          </span>
          <span className="numeral text-xs font-black text-[#0F172A]">
            {formatStat(player.minutes_avg_last_5, 0)}
          </span>
        </div>
        <div className="py-2.5">
          <span className="block text-[9px] font-black uppercase tracking-wider text-[#64748B]">
            Reliability
          </span>
          <span className="numeral text-xs font-black text-[#059669]">
            {reliability !== null ? `${Math.round(reliability * 100)}%` : "N/A"}
          </span>
        </div>
      </div>
    </Card>
  );
}
