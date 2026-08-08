import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowUpDown, Users } from "lucide-react";
import { usePredictions } from "@/hooks/useApi";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { UpcomingFixtures } from "@/components/UpcomingFixtures";
import { SearchInput } from "@/components/ui/SearchInput";
import { Dropdown } from "@/components/ui/overlays";
import { Skeleton, Badge } from "@/components/ui/primitives";
import { ErrorState, EmptyState } from "@/components/states";
import { formatPrice, formatStat } from "@/lib/format";
import { cn } from "@/lib/utils";

type SortKey = "predicted_total_points" | "value" | "total_points_avg_last_3" | "name";

const COLUMNS: { key: SortKey; label: string; hideMobile?: boolean }[] = [
  { key: "name", label: "Player" },
  { key: "value", label: "Price", hideMobile: true },
  { key: "total_points_avg_last_3", label: "Form", hideMobile: true },
  { key: "predicted_total_points", label: "xPts" },
];

export default function Players() {
  const { data, loading, error, refetch } = usePredictions();
  const [query, setQuery] = useState("");
  const [posFilter, setPosFilter] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("predicted_total_points");
  const [sortDesc, setSortDesc] = useState(true);

  const players = data?.predictions ?? [];

  const posOptions = useMemo(() => {
    const positions = Array.from(new Set(players.map((p) => p.position).filter(Boolean))) as string[];
    return [
      { value: "all", label: "All Positions" },
      ...positions.sort().map((p) => ({ value: p, label: p })),
    ];
  }, [players]);

  const filtered = useMemo(() => {
    const list = players
      .filter((p) => posFilter === "all" || p.position === posFilter)
      .filter((p) => {
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
  }, [players, query, posFilter, sortKey, sortDesc]);

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDesc((d) => !d);
    } else {
      setSortKey(key);
      setSortDesc(true);
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-5 py-8 pb-safe-bottom lg:px-8">
      {/* Header */}
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-signal/10 text-signal">
          <Users size={18} />
        </div>
        <div>
          <h1 className="font-display text-2xl font-bold text-ink sm:text-3xl">Players</h1>
          <p className="text-sm text-ink-tertiary">
            Every tracked player, sourced from the latest prediction run.
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="flex-1 max-w-sm">
          <SearchInput value={query} onChange={setQuery} placeholder="Search by name or team…" />
        </div>
        <Dropdown label="Position" options={posOptions} value={posFilter} onChange={setPosFilter} />
      </div>

      {/* Count */}
      {!loading && !error && filtered.length > 0 && (
        <div className="mb-3 text-xs text-ink-tertiary">
          {filtered.length} of {players.length} players
        </div>
      )}

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
        <div className="overflow-hidden rounded-xl border border-border-soft bg-surface">
          {/* Table header */}
          <div className="grid grid-cols-[1fr_auto_auto_auto] gap-4 border-b border-border-soft bg-surface-elevated px-4 py-2.5 sm:px-5">
            {COLUMNS.map((col) => (
              <button
                key={col.key}
                onClick={() => toggleSort(col.key)}
                className={cn(
                  "flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-ink-tertiary transition-colors hover:text-ink",
                  sortKey === col.key && "text-emerald",
                  col.key !== "name" && "justify-end",
                  col.hideMobile && "hidden sm:flex",
                )}
              >
                {col.label}
                <ArrowUpDown size={10} />
              </button>
            ))}
          </div>

          {/* Table body */}
          <ul>
            {filtered.map((p, i) => (
              <motion.li
                key={p.element ?? p.name ?? i}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.2, delay: Math.min(i * 0.015, 0.3) }}
                className="border-b border-border-soft last:border-b-0"
              >
                <Link
                  to={`/players/${encodeURIComponent(p.element !== undefined ? String(p.element) : p.name ?? "")}`}
                  className="grid grid-cols-[1fr_auto_auto_auto] items-center gap-4 px-4 py-2.5 transition-colors hover:bg-surface-hover sm:px-5"
                >
                  {/* Player cell */}
                  <div className="flex min-w-0 items-center gap-3">
                    <PlayerAvatar name={p.name} photoUrl={p.photo_url} size="sm" />
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="truncate text-sm font-medium text-ink">{p.name ?? "N/A"}</span>
                        {p.position && (
                          <span className="hidden rounded bg-white/5 px-1 py-0.5 text-[9px] font-semibold uppercase text-ink-tertiary sm:inline">
                            {p.position}
                          </span>
                        )}
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <TeamBadge team={p.team} logoUrl={p.team_logo_url} size="sm" />
                        <UpcomingFixtures player={p} variant="inline" maxFixtures={3} />
                      </div>
                    </div>
                  </div>

                  {/* Price */}
                  <span className="numeral hidden text-right text-sm text-ink-secondary sm:block">
                    {formatPrice(p.value)}
                  </span>

                  {/* Form */}
                  <span className="numeral hidden text-right text-sm text-ink-secondary sm:block">
                    {formatStat(p.total_points_avg_last_3)}
                  </span>

                  {/* xPts */}
                  <span className="numeral text-right">
                    <Badge tone="gold">{formatStat(p.predicted_total_points)}</Badge>
                  </span>
                </Link>
              </motion.li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
