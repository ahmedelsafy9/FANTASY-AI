import { Link } from "react-router-dom";
import {
  Sparkles,
  Trophy,
  Shield,
  ArrowRight,
  Zap,
  Crown,
  Calendar,
  Users,
  TrendingUp,
} from "lucide-react";
import { useTopPlayers, useCaptain, useMatchPredictions } from "@/hooks/useApi";
import { PlayerCard } from "@/components/PlayerCard";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { ExpectedPoints } from "@/components/ExpectedPoints";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { LowOwnershipBadge } from "@/components/LowOwnershipBadge";
import { deriveConfidenceLevel } from "@/lib/insights";
import { PlayerCardSkeleton, ErrorState } from "@/components/states";
import { Button, Card } from "@/components/ui/primitives";
import { formatPrice } from "@/lib/format";

export default function Home() {
  const { data: topData, loading: topLoading, error: topError, refetch: refetchTop } = useTopPlayers(6);
  const { data: capData, loading: capLoading } = useCaptain();
  const { data: matchData } = useMatchPredictions();

  const topPlayers = topData?.predictions ?? [];
  const targetGw = topData?.predicted_gameweek ?? topPlayers[0]?.predicted_for_gw ?? 1;

  const captain = capData?.recommendation;
  const featuredPick = topPlayers.find((p) => p.name !== captain?.name) ?? topPlayers[0];
  const featuredMatch = matchData?.predictions?.[0];

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 pb-safe-bottom sm:px-6 lg:px-8 space-y-10">
      {/* Hero Section — EPL Broadcast Studio */}
      <section className="relative overflow-hidden rounded-2xl border border-[#452477]/20 bg-gradient-to-br from-[#452477] via-[#381B62] to-[#250F43] p-6 sm:p-10 text-white shadow-card">
        {/* Subtle pitch line / architectural watermark */}
        <div className="absolute -right-16 -top-16 h-72 w-72 rounded-full bg-[#7041C5]/30 blur-2xl pointer-events-none" />
        <div className="absolute right-12 bottom-0 w-64 h-32 opacity-10 pointer-events-none border border-white/40 rounded-t-full" />

        <div className="relative z-10 max-w-3xl">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 backdrop-blur-sm px-3.5 py-1 text-xs font-black text-[#EEE7FA] shadow-sm mb-4">
            <Sparkles size={14} className="text-[#B9DDF5]" />
            <span>Gameweek {targetGw} Intelligence</span>
          </div>

          {/* Heading */}
          <h1 className="font-display text-3xl font-black text-white sm:text-5xl leading-[1.15] tracking-tight">
            Make Confident FPL Decisions <span className="text-[#B9DDF5]">Every Gameweek</span>
          </h1>

          <p className="mt-3 text-base font-medium text-[#EEE7FA]/90 sm:text-lg leading-relaxed max-w-2xl">
            Clear whole-number expected points, honest confidence ratings, and data-backed picks — designed to help you win your mini-league.
          </p>

          {/* Primary Action Buttons */}
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <Link to="/players">
              <Button size="lg" className="gap-2 text-sm font-black bg-[#7041C5] hover:bg-[#5D32A8] text-white border border-[#8C60DF]">
                <Users size={18} />
                <span>Find Your Next Pick</span>
              </Button>
            </Link>

            <Link to="/squad">
              <Button size="lg" className="gap-2 text-sm font-black bg-white/15 hover:bg-white/25 text-white border border-white/25 backdrop-blur-sm">
                <Shield size={18} className="text-[#B9DDF5]" />
                <span>Optimize Squad</span>
              </Button>
            </Link>

            <Link to="/captain">
              <Button size="lg" className="gap-2 text-sm font-black bg-[#EEE7FA] text-[#452477] hover:bg-white border border-transparent">
                <Crown size={18} className="text-[#B58A18]" />
                <span>Captain Pick</span>
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Gameweek Decision Spotlight (Captain, Top Pick, Featured Match) */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-black text-[#19171D] flex items-center gap-2">
            <Zap size={20} className="text-[#B58A18]" />
            <span>Key Decisions for Gameweek {targetGw}</span>
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Spotlight 1: Recommended Captain */}
          <Card className="flex flex-col justify-between border-[#E5D08E] bg-gradient-to-br from-[#FDF8EC]/60 via-white to-white p-5 shadow-sm hover:border-[#B58A18] transition-colors">
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-[#FDF8EC] border border-[#E5D08E] px-2.5 py-0.5 text-[10px] font-black uppercase text-[#8C680E]">
                  <Crown size={12} className="text-[#B58A18]" />
                  Captain Pick
                </span>
                <span className="text-[10px] font-bold text-[#6F6A76]">2× Points</span>
              </div>

              {captain ? (
                <div className="flex items-center gap-3">
                  <PlayerAvatar
                    name={captain.name}
                    photoUrl={captain.photo_url}
                    size="lg"
                    className="ring-2 ring-[#B58A18]"
                  />
                  <div className="min-w-0 flex-1">
                    <h3 className="font-display font-black text-base text-[#19171D] truncate">
                      {captain.name}
                    </h3>
                    <div className="flex items-center gap-2 mt-0.5 text-xs text-[#6F6A76] font-semibold">
                      <TeamBadge team={captain.team} logoUrl={captain.team_logo_url} size="sm" showName />
                      <ConfidenceBadge level={deriveConfidenceLevel(captain)} showTooltip={false} />
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <ExpectedPoints
                      points={captain.predicted_expected_points ?? captain.predicted_total_points}
                      size="sm"
                    />
                  </div>
                </div>
              ) : (
                <div className="text-sm font-semibold text-[#6F6A76] py-2">
                  {capLoading ? "Calculating captain pick..." : "Captain recommendation ready"}
                </div>
              )}

              {capData?.reasoning && (
                <p className="mt-3 text-xs font-semibold text-[#6F6A76] line-clamp-2">
                  {capData.reasoning}
                </p>
              )}
            </div>

            <Link to="/captain" className="mt-4 pt-3 border-t border-[#E8E3ED] flex items-center justify-between text-xs font-bold text-[#8C680E] hover:underline">
              <span>View full captain analysis</span>
              <ArrowRight size={14} />
            </Link>
          </Card>

          {/* Spotlight 2: Top Projected Performer */}
          <Card className="flex flex-col justify-between border-[#D4C3ED] bg-gradient-to-br from-[#EEE7FA]/50 via-white to-white p-5 shadow-sm hover:border-[#7041C5] transition-colors">
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-[#EEE7FA] border border-[#D4C3ED] px-2.5 py-0.5 text-[10px] font-black uppercase text-[#452477]">
                  <TrendingUp size={12} className="text-[#7041C5]" />
                  Top Projected Pick
                </span>
                {featuredPick && (
                  <LowOwnershipBadge
                    ownership={featuredPick.selected_by_percent ?? (featuredPick as Record<string, unknown>).ownership_pct as number | undefined}
                    predictedPoints={featuredPick.predicted_expected_points ?? featuredPick.predicted_total_points}
                  />
                )}
              </div>

              {featuredPick ? (
                <div className="flex items-center gap-3">
                  <PlayerAvatar
                    name={featuredPick.name}
                    photoUrl={featuredPick.photo_url}
                    size="lg"
                    className="ring-2 ring-[#7041C5]"
                  />
                  <div className="min-w-0 flex-1">
                    <h3 className="font-display font-black text-base text-[#19171D] truncate">
                      {featuredPick.name}
                    </h3>
                    <div className="flex items-center gap-2 mt-0.5 text-xs text-[#6F6A76] font-semibold">
                      <span>{featuredPick.team}</span>
                      <span>•</span>
                      <span className="text-[#452477] font-bold">
                        £{formatPrice(featuredPick.value ?? (typeof featuredPick.now_cost === "number" ? featuredPick.now_cost : 50))}
                      </span>
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <ExpectedPoints
                      points={featuredPick.predicted_expected_points ?? featuredPick.predicted_total_points}
                      size="sm"
                    />
                  </div>
                </div>
              ) : (
                <div className="text-sm font-semibold text-[#6F6A76] py-2">
                  Projecting top performers for Gameweek {targetGw}...
                </div>
              )}

              <p className="mt-3 text-xs font-semibold text-[#6F6A76]">
                High-confidence pick evaluated on xG/xA form, minutes security, and fixture strength.
              </p>
            </div>

            <Link to="/players" className="mt-4 pt-3 border-t border-[#E8E3ED] flex items-center justify-between text-xs font-bold text-[#7041C5] hover:underline">
              <span>Explore all projected players</span>
              <ArrowRight size={14} />
            </Link>
          </Card>

          {/* Spotlight 3: Featured Match */}
          <Card className="flex flex-col justify-between border-[#E8E3ED] bg-gradient-to-br from-[#F8F7FA] via-white to-white p-5 shadow-sm hover:border-[#7041C5]/50 transition-colors">
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-[#F4F3F6] border border-[#E8E3ED] px-2.5 py-0.5 text-[10px] font-black uppercase text-[#19171D]">
                  <Calendar size={12} className="text-[#6F6A76]" />
                  Featured Match
                </span>
                {featuredMatch && (
                  <span className="text-[10px] font-black text-[#7041C5] uppercase">
                    {featuredMatch.confidence_level} Conf
                  </span>
                )}
              </div>

              {featuredMatch ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between py-1">
                    <span className="font-display font-black text-sm text-[#19171D]">
                      {featuredMatch.home_team}
                    </span>
                    <span className="font-mono text-base font-black text-[#19171D] px-2 py-0.5 rounded bg-[#F4F3F6] border border-[#E8E3ED]">
                      {featuredMatch.predicted_scoreline}
                    </span>
                    <span className="font-display font-black text-sm text-[#19171D]">
                      {featuredMatch.away_team}
                    </span>
                  </div>
                  <div className="text-center text-xs font-semibold text-[#6F6A76]">
                    {featuredMatch.predicted_result === "HOME_WIN"
                      ? `${featuredMatch.home_team} favored (${Math.round(featuredMatch.home_win_probability * 100)}%)`
                      : featuredMatch.predicted_result === "AWAY_WIN"
                      ? `${featuredMatch.away_team} favored (${Math.round(featuredMatch.away_win_probability * 100)}%)`
                      : "Close contest / Draw predicted"}
                  </div>
                </div>
              ) : (
                <div className="text-sm font-semibold text-[#6F6A76] py-2">
                  Match predictions compiling...
                </div>
              )}
            </div>

            <Link to="/match-predictions" className="mt-4 pt-3 border-t border-[#E8E3ED] flex items-center justify-between text-xs font-bold text-[#452477] hover:underline">
              <span>View all match predictions</span>
              <ArrowRight size={14} />
            </Link>
          </Card>
        </div>
      </section>

      {/* Top Projected Scorers */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-black text-[#19171D] flex items-center gap-2">
              <Trophy size={22} className="text-[#B58A18]" />
              <span>Top Projected Scorers</span>
            </h2>
            <p className="text-sm font-semibold text-[#6F6A76] mt-0.5">
              Highest predicted points for Gameweek {targetGw} based on recent form and upcoming opposition.
            </p>
          </div>

          <Link to="/players">
            <Button variant="secondary" size="sm" className="gap-1.5 font-bold">
              <span>All Players</span>
              <ArrowRight size={15} />
            </Button>
          </Link>
        </div>

        {topLoading && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <PlayerCardSkeleton key={i} />
            ))}
          </div>
        )}

        {!topLoading && topError && (
          <ErrorState message={topError} onRetry={refetchTop} />
        )}

        {!topLoading && !topError && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {topPlayers.map((player, idx) => (
              <PlayerCard
                key={player.element ?? player.name}
                player={player}
                rank={idx + 1}
                linkToDetail={true}
              />
            ))}
          </div>
        )}
      </section>

      {/* Trust & Principles Section */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-3 pt-2">
        <Card className="p-5 border border-[#E8E3ED]">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#EEE7FA] text-[#452477] border border-[#D4C3ED] mb-3 shadow-sm">
            <Sparkles size={20} />
          </div>
          <h3 className="text-base font-black text-[#19171D] mb-1">Expected Points Projections</h3>
          <p className="text-xs font-semibold text-[#6F6A76] leading-relaxed">
            Considers playing time security, recent form, underlying xG/xA, and opponent difficulty to project realistic points.
          </p>
        </Card>

        <Card className="p-5 border border-[#E8E3ED]">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#FDF8EC] text-[#8C680E] border border-[#E5D08E] mb-3 shadow-sm">
            <Shield size={20} />
          </div>
          <h3 className="text-base font-black text-[#19171D] mb-1">Transparent Confidence</h3>
          <p className="text-xs font-semibold text-[#6F6A76] leading-relaxed">
            Confidence badges tell you how strong and consistent the signals are — not false accuracy promises.
          </p>
        </Card>

        <Card className="p-5 border border-[#E8E3ED]">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#EEF7FC] text-[#1E4D6B] border border-[#B9DDF5] mb-3 shadow-sm">
            <TrendingUp size={20} />
          </div>
          <h3 className="text-base font-black text-[#19171D] mb-1">Squad Builder Optimization</h3>
          <p className="text-xs font-semibold text-[#6F6A76] leading-relaxed">
            Construct mathematically optimal 15-player squads under the £100m budget cap based on synchronized expected points.
          </p>
        </Card>
      </section>
    </div>
  );
}
