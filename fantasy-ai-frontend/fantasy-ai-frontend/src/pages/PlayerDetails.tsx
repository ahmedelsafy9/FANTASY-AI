import { useParams, Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { usePredictions } from "@/hooks/useApi";
import { PlayerDetailPanel } from "@/components/PlayerDetailPanel";
import { PlayerProfileSkeleton, ErrorState, EmptyState } from "@/components/states";
import { Button } from "@/components/ui/primitives";

export default function PlayerDetails() {
  const { id } = useParams<{ id: string }>();
  const { data, loading, error, refetch } = usePredictions(id);
  const player = data?.predictions?.[0];

  return (
    <div className="mx-auto max-w-3xl px-5 py-10 pb-24 lg:px-8">
      <Link to="/players">
        <Button variant="ghost" size="sm" className="mb-6">
          <ArrowLeft size={14} /> Back to Players
        </Button>
      </Link>

      {loading && <PlayerProfileSkeleton />}
      {!loading && error && <ErrorState message={error} onRetry={refetch} />}
      {!loading && !error && !player && (
        <EmptyState title="Player not found" description="This player may not be in the current dataset." />
      )}
      {!loading && !error && player && <PlayerDetailPanel player={player} />}
    </div>
  );
}
