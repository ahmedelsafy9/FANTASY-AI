import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import type { PlayerRecord } from "@/types/api";
import { PredictionRank } from "@/components/PredictionRank";
import { RankRowSkeleton, ErrorState, EmptyState } from "@/components/states";
import { Button } from "@/components/ui/primitives";

interface TopPredictionsProps {
  players: PlayerRecord[] | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  onSelect: (player: PlayerRecord) => void;
}

export function TopPredictions({ players, loading, error, onRetry, onSelect }: TopPredictionsProps) {
  return (
    <section className="mx-auto max-w-4xl px-5 py-14 lg:px-8">
      <div className="mb-8 flex items-end justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-ink sm:text-3xl">Top AI Picks</h2>
          <p className="mt-1.5 text-sm text-ink-tertiary">
            Ranked by predicted points for the next Gameweek.
          </p>
        </div>
        <Link to="/predictions" className="hidden sm:block">
          <Button variant="ghost" size="sm">
            View all <ArrowRight size={14} />
          </Button>
        </Link>
      </div>

      {loading && (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <RankRowSkeleton key={i} />
          ))}
        </div>
      )}

      {!loading && error && <ErrorState message={error} onRetry={onRetry} />}

      {!loading && !error && players && players.length === 0 && (
        <EmptyState title="No predictions available yet" description="Run the training pipeline to generate predictions." />
      )}

      {!loading && !error && players && players.length > 0 && (
        <PredictionRank players={players} onSelect={onSelect} />
      )}
    </section>
  );
}
