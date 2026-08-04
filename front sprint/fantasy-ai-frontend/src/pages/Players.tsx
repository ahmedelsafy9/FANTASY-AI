import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpDown } from "lucide-react";
import type { PlayerRecord } from "@/types/api";
import { usePredictions } from "@/hooks/useApi";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { SearchInput } from "@/components/ui/SearchInput";
import { Skeleton, Badge } from "@/components/ui/primitives";
import { ErrorState, EmptyState } from "@/components/states";
import { formatPrice, formatStat } from "@/lib/format";
import { cn } from "@/lib/utils";

type SortKey = "predicted_total_points" | "value" | "total_points_avg_last_3" | "name";

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: "name", label: "Player" },
  { key: "value", label: "Price" },
  { key: "total_points_avg_last_3", label: "Form" },
  { key: "predicted_total_points", label: "xPts" },
];

export default function Players() {
  const { data, loading, error, refetch } = usePredictions();
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("predicted_total_points");
  const [sortDesc, setSortDesc] = useState(true);

  const players = data?.predictions ?? [];

  const filtered = useMemo(() => {
    const list = players.filter((p) => {
      if (!query.trim()) return true;
      const q = query.toLowerCase();
      return p.name?.toLowerCase().includes(q) || p.team?.toLowerCase().includes(q);
    });
    return [...list].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === "string" || typeof bv === "string") {
        const cmp = String(av ?? "").localeCompare(String(bv ?? ""));
        return sortDesc ? -cmp : cmp;
      }
      const an = typeof av === "number" ? av : -Infinity;
      const bn = typeof bv === "number" ? bv : -Infinity;
      return sortDesc ? bn - an : an - bn;
    });
  }, [players, query, sortKey, sortDesc]);

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDesc((d) => !d);
    } else {
      setSortKey(key);
      setSortDesc(true);
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-5 py-10 pb-24 lg:px-8">
      <div className="mb-2 flex flex-col gap-1">
        <h1 className="text-3xl font-semibold text-ink">Players</h1>
        <p className="text-sm text-ink-tertiary">
          Every tracked player, sourced from the latest prediction run.
        </p>
      </div>

      <div className="mb-6 mt-6 max-w-sm">
        <SearchInput value={query} onChange={setQuery} placeholder="Search by name or team…" />
      </div>

      {loading && (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full rounded-xl" />
          ))}
        </div>
      )}

      {!loading && error && <ErrorState message={error} onRetry={refetch} />}

      {!loading && !error && filtered.length === 0 && (
        <EmptyState title="No players match your search" />
      )}

      {!loading && !error && filtered.length > 0 && (
        <div className="overflow-hidden rounded-2xl border border-border-soft bg-surface">
          <div className="grid grid-cols-[1fr_auto_auto_auto] gap-4 border-b border-border-soft bg-surface-elevated px-5 py-3">
            {COLUMNS.map((col) => (
              <button
                key={col.key}
                onClick={() => toggleSort(col.key)}
                className={cn(
                  "flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-ink-tertiary transition-colors hover:text-ink",
                  sortKey === col.key && "text-gold",
                  col.key !== "name" && "justify-end",
                )}
              >
                {col.label}
                <ArrowUpDown size={11} />
              </button>
            ))}
          </div>
          <ul>
            {filtered.map((p) => (
              <PlayerRow key={p.element ?? p.name} player={p} />
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function PlayerRow({ player }: { player: PlayerRecord }) {
  const id = player.element !== undefined ? String(player.element) : player.name ?? "";
  return (
    <li className="border-b border-border-soft last:border-b-0">
      <Link
        to={`/players/${encodeURIComponent(id)}`}
        className="grid grid-cols-[1fr_auto_auto_auto] items-center gap-4 px-5 py-3 transition-colors hover:bg-surface-hover"
      >
        <div className="flex min-w-0 items-center gap-3">
          <PlayerAvatar name={player.name} size="sm" />
          <div className="min-w-0">
            <div className="truncate text-sm font-medium text-ink">{player.name ?? "N/A"}</div>
            <TeamBadge team={player.team} size="sm" showName />
          </div>
        </div>
        <span className="numeral text-right text-sm text-ink-secondary">{formatPrice(player.value)}</span>
        <span className="numeral text-right text-sm text-ink-secondary">
          {formatStat(player.total_points_avg_last_3)}
        </span>
        <span className="numeral text-right">
          <Badge tone="gold">{formatStat(player.predicted_total_points)}</Badge>
        </span>
      </Link>
    </li>
  );
}
