import { Link } from "react-router-dom";
import {
  Sparkles,
  Trophy,
  Shield,
  ArrowRight,
  Zap,
  Crown,
  Flame,
  Calendar,
  Users,
} from "lucide-react";
import { useTopPlayers, useCaptain, useDifferentials, useMatchPredictions } from "@/hooks/useApi";
import { PlayerCard } from "@/components/PlayerCard";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { ExpectedPoints } from "@/components/ExpectedPoints";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { deriveConfidenceLevel } from "@/lib/insights";
import { PlayerCardSkeleton, ErrorState } from "@/components/states";
import { Button, Card } from "@/components/ui/primitives";
import { formatPrice } from "@/lib/format";

export default function Home() {
  const { data: topData, loading: topLoading, error: topError, refetch: refetchTop } = useTopPlayers(6);
  const { data: capData, loading: capLoading } = useCaptain();
  const { data: diffData } = useDifferentials({ limit: 1 });
  const { data: matchData } = useMatchPredictions();

  const topPlayers = topData?.predictions ?? [];
  const targetGw = topData?.predicted_gameweek ?? topPlayers[0]?.predicted_for_gw ?? 1;

  const captain = capData?.recommendation;
  const differential = diffData?.predictions?.[0];
  const featuredMatch = matchData?.predictions?.[0];

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 pb-safe-bottom sm:px-6 lg:px-8 space-y-10">
      {/* Hero Section — Assistant Hub */}
      <section className="relative overflow-hidden rounded-2xl border border-[#E2E8F0] bg-white p-6 sm:p-10 shadow-soft">
        <div className="absolute -right-16 -top-16 h-72 w-72 rounded-full bg-[#ECFDF5] opacity-60 pointer-events-none" />

        <div className="relative z-10 max-w-3xl">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 rounded-full border border-[#A7F3D0] bg-[#ECFDF5] px-3.5 py-1 text-xs font-black text-[#059669] shadow-sm mb-4">
            <Sparkles size={14} className="fill-[#10B981] text-[#10B981]" />
            <span>Gameweek {targetGw} Assistant</span>
          </div>

          {/* Heading */}
          <h1 className="font-display text-3xl font-black text-[#0F172A] sm:text-5xl leading-[1.15] tracking-tight">
            Make Confident FPL Decisions <span className="text-[#10B981]">Every Gameweek</span>
          </h1>

          <p className="mt-3 text-base font-semibold text-[#475569] sm:text-lg leading-relaxed max-w-2xl">
            Clear expected points, honest confidence ratings, and data-backed picks — designed to help you win your mini-league.
          </p>

          {/* Primary Action Buttons */}
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <Link to="/players">
              <Button size="lg" className="gap-2 text-sm font-black">
                <Users size={18} />
                <span>Find Your Next Pick</span>
              </Button>
            </Link>

            <Link to="/squad">
              <Button variant="secondary" size="lg" className="gap-2 text-sm font-black">
                <Shield size={18} className="text-[#10B981]" />
                <span>Optimize Squad</span>
              </Button>
            </Link>

            <Link to="/captain">
              <Button variant="ghost" size="lg" className="gap-2 text-sm font-bold text-[#D97706] hover:bg-[#FFFBEB]">
                <Crown size={18} />
                <span>Captain Pick</span>
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Gameweek Decision Spotlight (Captain, Differential, Key Match) */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-black text-[#0F172A] flex items-center gap-2">
            <Zap size={20} className="text-[#F59E0B]" />
            <span>Key Decisions for Gameweek {targetGw}</span>
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Spotlight 1: Recommended Captain */}
          <Card className="flex flex-col justify-between border-[#FDE68A] bg-gradient-to-br from-[#FFFBEB] via-white to-white p-5 shadow-soft hover:border-[#F59E0B] transition-colors">
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-[#FEF3C7] border border-[#FDE68A] px-2.5 py-0.5 text-[10px] font-black uppercase text-[#92400E]">
                  <Crown size={12} className="text-[#F59E0B]" />
                  Captain Pick
                </span>
                <span className="text-[10px] font-bold text-[#64748B]">2× Points</span>
              </div>

              {captain ? (
                <div className="flex items-center gap-3">
                  <PlayerAvatar
                    name={captain.name}
                    photoUrl={captain.photo_url}
                    size="lg"
                    className="ring-2 ring-[#F59E0B]"
                  />
                  <div className="min-w-0 flex-1">
                    <h3 className="font-display font-black text-base text-[#0F172A] truncate">
                      {captain.name}
                    </h3>
                    <div className="flex items-center gap-2 mt-0.5 text-xs text-[#64748B] font-semibold">
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
                <div className="text-sm font-semibold text-[#64748B] py-2">
                  {capLoading ? "Calculating captain pick..." : "Captain recommendation ready"}
                </div>
              )}

              {capData?.reasoning && (
                <p className="mt-3 text-xs font-semibold text-[#475569] line-clamp-2">
                  {capData.reasoning}
                </p>
              )}
            </div>

            <Link to="/captain" className="mt-4 pt-3 border-t border-[#F1F5F9] flex items-center justify-between text-xs font-bold text-[#D97706] hover:underline">
              <span>View full captain analysis</span>
              <ArrowRight size={14} />
            </Link>
          </Card>

          {/* Spotlight 2: Top Differential */}
          <Card className="flex flex-col justify-between border-[#A7F3D0] bg-gradient-to-br from-[#ECFDF5] via-white to-white p-5 shadow-soft hover:border-[#10B981] transition-colors">
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-[#ECFDF5] border border-[#A7F3D0] px-2.5 py-0.5 text-[10px] font-black uppercase text-[#059669]">
                  <Flame size={12} className="text-[#10B981]" />
                  Breakout Differential
                </span>
                {differential && (
                  <span className="text-[10px] font-mono font-bold text-[#0284C7] bg-[#F0F9FF] border border-[#BAE6FD] px-1.5 py-0.5 rounded">
                    {(differential.ownership_pct ?? 10).toFixed(1)}% owned
                  </span>
                )}
              </div>

              {differential ? (
                <div className="flex items-center gap-3">
                  <PlayerAvatar
                    name={differential.name}
                    photoUrl={differential.photo_url}
                    size="lg"
                    className="ring-2 ring-[#10B981]"
                  />
                  <div className="min-w-0 flex-1">
                    <h3 className="font-display font-black text-base text-[#0F172A] truncate">
                      {differential.name}
                    </h3>
                    <div className="flex items-center gap-2 mt-0.5 text-xs text-[#64748B] font-semibold">
                      <span>{differential.team}</span>
                      <span>•</span>
                      <span className="text-[#059669] font-bold">
                        £{formatPrice(differential.value ?? (differential.price ? differential.price * 10 : 50))}
                      </span>
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <ExpectedPoints
                      points={differential.predicted_expected_points}
                      size="sm"
                    />
                  </div>
                </div>
              ) : (
                <div className="text-sm font-semibold text-[#64748B] py-2">
                  Scanning for low-ownership breakout gems...
                </div>
              )}

              <p className="mt-3 text-xs font-semibold text-[#475569]">
                High ceiling asset to help you climb in your mini-league.
              </p>
            </div>

            <Link to="/differentials" className="mt-4 pt-3 border-t border-[#F1F5F9] flex items-center justify-between text-xs font-bold text-[#059669] hover:underline">
              <span>Explore all differentials</span>
              <ArrowRight size={14} />
            </Link>
          </Card>

          {/* Spotlight 3: Featured Match */}
          <Card className="flex flex-col justify-between border-[#CBD5E1] bg-gradient-to-br from-[#F8FAFC] via-white to-white p-5 shadow-soft hover:border-[#94A3B8] transition-colors">
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-[#F1F5F9] border border-[#CBD5E1] px-2.5 py-0.5 text-[10px] font-black uppercase text-[#334155]">
                  <Calendar size={12} className="text-[#64748B]" />
                  Featured Match
                </span>
                {featuredMatch && (
                  <span className="text-[10px] font-black text-[#10B981] uppercase">
                    {featuredMatch.confidence_level} Conf
                  </span>
                )}
              </div>

              {featuredMatch ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between py-1">
                    <span className="font-display font-black text-sm text-[#0F172A]">
                      {featuredMatch.home_team}
                    </span>
                    <span className="font-mono text-base font-black text-[#0F172A] px-2 py-0.5 rounded bg-[#F1F5F9]">
                      {featuredMatch.predicted_scoreline}
                    </span>
                    <span className="font-display font-black text-sm text-[#0F172A]">
                      {featuredMatch.away_team}
                    </span>
                  </div>
                  <div className="text-center text-xs font-semibold text-[#64748B]">
                    {featuredMatch.predicted_result === "HOME_WIN"
                      ? `${featuredMatch.home_team} favored (${Math.round(featuredMatch.home_win_probability * 100)}%)`
                      : featuredMatch.predicted_result === "AWAY_WIN"
                      ? `${featuredMatch.away_team} favored (${Math.round(featuredMatch.away_win_probability * 100)}%)`
                      : "Close contest / Draw predicted"}
                  </div>
                </div>
              ) : (
                <div className="text-sm font-semibold text-[#64748B] py-2">
                  Match predictions compiling...
                </div>
              )}
            </div>

            <Link to="/match-predictions" className="mt-4 pt-3 border-t border-[#F1F5F9] flex items-center justify-between text-xs font-bold text-[#475569] hover:underline">
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
            <h2 className="text-2xl font-black text-[#0F172A] flex items-center gap-2">
              <Trophy size={22} className="text-[#F59E0B]" />
              <span>Top Projected Scorers</span>
            </h2>
            <p className="text-sm font-semibold text-[#64748B] mt-0.5">
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
        <Card className="p-5 border border-[#E2E8F0]">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0] mb-3 shadow-sm">
            <Sparkles size={20} />
          </div>
          <h3 className="text-base font-black text-[#0F172A] mb-1">Expected Points Projections</h3>
          <p className="text-xs font-semibold text-[#475569] leading-relaxed">
            Considers playing time security, recent form, underlying xG/xA, and opponent difficulty to project realistic points.
          </p>
        </Card>

        <Card className="p-5 border border-[#E2E8F0]">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#FFFBEB] text-[#92400E] border border-[#FDE68A] mb-3 shadow-sm">
            <Shield size={20} />
          </div>
          <h3 className="text-base font-black text-[#0F172A] mb-1">Transparent Confidence</h3>
          <p className="text-xs font-semibold text-[#475569] leading-relaxed">
            Confidence badges tell you how strong and consistent the signals are — not false accuracy promises.
          </p>
        </Card>

        <Card className="p-5 border border-[#E2E8F0]">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#EEF2FF] text-[#4F46E5] border border-indigo-200 mb-3 shadow-sm">
            <Flame size={20} />
          </div>
          <h3 className="text-base font-black text-[#0F172A] mb-1">Smart Differentials</h3>
          <p className="text-xs font-semibold text-[#475569] leading-relaxed">
            Identifies low-ownership assets with high upside so you can find gems before the rest of your league catches on.
          </p>
        </Card>
      </section>
    </div>
  );
}
