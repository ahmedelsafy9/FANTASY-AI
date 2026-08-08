import { Link } from "react-router-dom";
import { Sparkles, Trophy, Shield, ArrowRight, Zap, Target, Flame } from "lucide-react";
import { useTopPlayers } from "@/hooks/useApi";
import { PlayerCard } from "@/components/PlayerCard";
import { PlayerCardSkeleton, ErrorState } from "@/components/states";
import { Button, Card } from "@/components/ui/primitives";

export default function Home() {
  const { data, loading, error, refetch } = useTopPlayers(3);
  const topPlayers = data?.predictions ?? [];

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Hero Section - Light gray / white card with clean typography */}
      <section className="relative overflow-hidden rounded-chunky-xl border border-[#E2E8F0] bg-white p-8 sm:p-12 shadow-card mb-12">
        {/* Subtle pale green background accent top-right */}
        <div className="absolute -right-16 -top-16 h-64 w-64 rounded-full bg-[#ECFDF5] opacity-70 pointer-events-none" />

        <div className="relative z-10 max-w-2xl">
          {/* AI Badge */}
          <div className="inline-flex items-center gap-2 rounded-full border border-[#A7F3D0] bg-[#ECFDF5] px-4 py-1.5 text-xs font-black text-[#059669] shadow-sm mb-6">
            <Zap size={15} className="fill-[#10B981] text-[#10B981]" />
            <span>POWERED BY ROOSTERS </span>
          </div>

          {/* Main Heading - Dark navy with green highlighted text */}
          <h1 className="font-display text-4xl font-black text-[#0F172A] sm:text-6xl leading-[1.1]">
            Build Your Winning <span className="text-[#10B981] font-black">Fantasy Squad</span>
          </h1>

          <p className="mt-4 text-base font-semibold text-[#475569] sm:text-lg leading-relaxed">
            Machine learning points predictions, fixture analytics, and instant team optimization for FPL managers.
          </p>

          {/* CTAs */}
          <div className="mt-8 flex flex-wrap items-center gap-4">
            <Link to="/squad">
              <Button size="lg" className="gap-2.5 text-base">
                <Shield size={20} />
                <span>Build My Squad</span>
              </Button>
            </Link>

            <Link to="/predictions">
              <Button variant="secondary" size="lg" className="gap-2.5 text-base">
                <Sparkles size={20} className="text-[#10B981]" />
                <span>View AI Predictions</span>
              </Button>
            </Link>
          </div>
        </div>

        {/* Decorative Feature Chips (Right Side Visuals) */}
        <div className="absolute right-8 top-1/2 -translate-y-1/2 hidden lg:flex flex-col gap-3.5 pointer-events-none">
          <div className="flex items-center gap-3.5 rounded-2xl border border-[#E2E8F0] bg-[#F8FAFC] p-4 shadow-sm">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0] font-black">
              <Flame size={20} />
            </div>
            <div>
              <div className="text-[10px] font-black uppercase text-[#64748B]">AI Model Accuracy</div>
              <div className="text-sm font-black text-[#0F172A]">High GW Reliability</div>
            </div>
          </div>

          <div className="flex items-center gap-3.5 rounded-2xl border border-[#FDE68A] bg-[#FFFBEB] p-4 shadow-sm ml-6">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#FEF3C7] text-[#92400E] font-black">
              <Target size={20} />
            </div>
            <div>
              <div className="text-[10px] font-black uppercase text-[#92400E]">Budget Optimizer</div>
              <div className="text-sm font-black text-[#0F172A]">Max £100.0m Value</div>
            </div>
          </div>
        </div>
      </section>

      {/* Top AI Expected Scorers Leaderboard */}
      <section className="mb-12">
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#FFFBEB] text-[#92400E] border border-[#FDE68A] shadow-sm">
                <Trophy size={18} />
              </div>
              <h2 className="text-2xl font-black text-[#0F172A]">
                Top AI Expected Scorers
              </h2>
            </div>
            <p className="text-sm font-semibold text-[#64748B] mt-1">
              Highest predicted points for the upcoming gameweek
            </p>
          </div>

          <Link to="/predictions" className="hidden sm:inline-flex">
            <Button variant="secondary" size="sm" className="gap-1.5 font-extrabold">
              <span>View All Predictions</span>
              <ArrowRight size={16} />
            </Button>
          </Link>
        </div>

        {loading && (
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <PlayerCardSkeleton key={i} />
            ))}
          </div>
        )}

        {!loading && error && <ErrorState message={error} onRetry={refetch} />}

        {!loading && !error && (
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {topPlayers.map((player, idx) => (
              <PlayerCard key={player.element ?? player.name} player={player} rank={idx + 1} />
            ))}
          </div>
        )}
      </section>

      {/* Feature Cards Grid */}
      <section className="grid grid-cols-1 gap-6 sm:grid-cols-3">
        <Card className="p-6 border border-[#E2E8F0] hover:border-[#A7F3D0]">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0] mb-4 shadow-sm">
            <Sparkles size={24} />
          </div>
          <h3 className="text-lg font-black text-[#0F172A] mb-2">Machine Learning Points</h3>
          <p className="text-sm font-semibold text-[#475569] leading-relaxed">
            Evaluates form, fixtures, minutes, and expected metrics to deliver reliable gameweek projections.
          </p>
        </Card>

        <Card className="p-6 border border-[#E2E8F0] hover:border-[#FDE68A]">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#FFFBEB] text-[#92400E] border border-[#FDE68A] mb-4 shadow-sm">
            <Shield size={24} />
          </div>
          <h3 className="text-lg font-black text-[#0F172A] mb-2">Smart Squad Optimizer</h3>
          <p className="text-sm font-semibold text-[#475569] leading-relaxed">
            Auto-picks optimal 15-player squads respecting position counts, £100m budget, and club limits.
          </p>
        </Card>

        <Card className="p-6 border border-[#E2E8F0] hover:border-indigo-200">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-700 border border-indigo-200 mb-4 shadow-sm">
            <Trophy size={24} />
          </div>
          <h3 className="text-lg font-black text-[#0F172A] mb-2">Captain Intelligence</h3>
          <p className="text-sm font-semibold text-[#475569] leading-relaxed">
            Identifies high-ceiling captain options to maximize your 2× points boost each gameweek.
          </p>
        </Card>
      </section>
    </div>
  );
}
