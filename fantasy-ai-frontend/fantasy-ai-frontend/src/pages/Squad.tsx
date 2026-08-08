import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Crown, Plus, Trash2, Shield, Users } from "lucide-react";
import type { PlayerRecord } from "@/types/api";
import { usePredictions } from "@/hooks/useApi";
import { useSquad } from "@/hooks/useSquad";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { UpcomingFixtures } from "@/components/UpcomingFixtures";
import { PlayerToken, EmptySlot } from "@/components/PlayerToken";
import { Pitch, PitchRow } from "@/components/Pitch";
import { Stat } from "@/components/stats";
import { Button, Badge, Skeleton } from "@/components/ui/primitives";
import { SearchInput } from "@/components/ui/SearchInput";
import { Dropdown } from "@/components/ui/overlays";
import { ErrorState, EmptyState } from "@/components/states";
import { formatPrice, formatStat } from "@/lib/format";

/**
 * Squad builder with visual pitch formation. Players are grouped by
 * position on a football pitch. Uses existing useSquad hook — no backend
 * changes, no fake persistence.
 */
export default function Squad() {
  const { data, loading, error, refetch } = usePredictions();
  const [query, setQuery] = useState("");
  const [posFilter, setPosFilter] = useState("all");
  const squadState = useSquad();

  const players = data?.predictions ?? [];

  const posOptions = useMemo(() => {
    const positions = Array.from(new Set(players.map((p) => p.position).filter(Boolean))) as string[];
    return [
      { value: "all", label: "All Positions" },
      ...positions.sort().map((p) => ({ value: p, label: p })),
    ];
  }, [players]);

  const filtered = useMemo(() => {
    return players
      .filter((p) => {
        if (posFilter !== "all" && p.position !== posFilter) return false;
        if (!query.trim()) return true;
        const q = query.toLowerCase();
        return p.name?.toLowerCase().includes(q) || p.team?.toLowerCase().includes(q);
      })
      .sort((a, b) => (b.predicted_total_points ?? -Infinity) - (a.predicted_total_points ?? -Infinity));
  }, [players, query, posFilter]);

  const captain = squadState.bestXI[0];

  // Group squad by position for pitch
  const gk = squadState.squad.filter((p) => p.position === "GKP" || p.position === "GK");
  const def = squadState.squad.filter((p) => p.position === "DEF");
  const mid = squadState.squad.filter((p) => p.position === "MID");
  const fwd = squadState.squad.filter((p) => p.position === "FWD");
  const unpositioned = squadState.squad.filter(
    (p) => !["GKP", "GK", "DEF", "MID", "FWD"].includes(p.position ?? ""),
  );

  return (
    <div className="mx-auto max-w-7xl px-5 py-6 pb-safe-bottom lg:px-8">
      {/* Header */}
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald/10 text-emerald">
          <Shield size={18} />
        </div>
        <div>
          <h1 className="font-display text-2xl font-bold text-ink sm:text-3xl">
            Squad Builder
          </h1>
          <p className="text-sm text-ink-tertiary">
            Select up to {squadState.maxSize} players. AI highlights your strongest XI.
          </p>
        </div>
      </div>

      {/* Squad summary bar */}
      <div className="mb-6 flex flex-wrap items-center gap-4 rounded-xl border border-border-soft bg-surface p-4">
        <div className="flex items-center gap-2">
          <Users size={16} className="text-emerald" />
          <Badge tone={squadState.isFull ? "teal" : "neutral"}>
            {squadState.squad.length}/{squadState.maxSize}
          </Badge>
        </div>
        <Stat label="Squad xPts" value={formatStat(squadState.totalExpectedPoints)} tone="gold" />
        <Stat label="Total Price" value={formatPrice(squadState.totalPrice)} />
        {captain && (
          <div className="flex items-center gap-2">
            <Crown size={14} className="text-gold" />
            <span className="text-xs font-medium text-ink-secondary">
              {captain.name ?? "N/A"}{" "}
              <span className="numeral text-gold">{formatStat(captain.predicted_total_points)}</span>
            </span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_380px]">
        {/* Pitch visualization */}
        <div>
          {squadState.squad.length > 0 ? (
            <Pitch className="mb-6 min-h-[380px] sm:min-h-[440px]">
              {/* GK row */}
              <PitchRow>
                {gk.length > 0
                  ? gk.map((p) => (
                      <PlayerToken
                        key={p.element ?? p.name}
                        player={p}
                        isCaptain={captain === p}
                        onClick={() => squadState.removePlayer(p)}
                      />
                    ))
                  : <EmptySlot label="GK" />}
              </PitchRow>

              {/* DEF row */}
              <PitchRow>
                {def.length > 0
                  ? def.map((p) => (
                      <PlayerToken
                        key={p.element ?? p.name}
                        player={p}
                        isCaptain={captain === p}
                        onClick={() => squadState.removePlayer(p)}
                      />
                    ))
                  : <EmptySlot label="DEF" />}
              </PitchRow>

              {/* MID row */}
              <PitchRow>
                {mid.length > 0
                  ? mid.map((p) => (
                      <PlayerToken
                        key={p.element ?? p.name}
                        player={p}
                        isCaptain={captain === p}
                        onClick={() => squadState.removePlayer(p)}
                      />
                    ))
                  : <EmptySlot label="MID" />}
              </PitchRow>

              {/* FWD row */}
              <PitchRow>
                {fwd.length > 0
                  ? fwd.map((p) => (
                      <PlayerToken
                        key={p.element ?? p.name}
                        player={p}
                        isCaptain={captain === p}
                        onClick={() => squadState.removePlayer(p)}
                      />
                    ))
                  : <EmptySlot label="FWD" />}
              </PitchRow>

              {/* Unpositioned / bench */}
              {unpositioned.length > 0 && (
                <PitchRow className="opacity-60">
                  {unpositioned.map((p) => (
                    <PlayerToken
                      key={p.element ?? p.name}
                      player={p}
                      onClick={() => squadState.removePlayer(p)}
                    />
                  ))}
                </PitchRow>
              )}
            </Pitch>
          ) : (
            <div className="mb-6 flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-emerald/20 bg-pitch-deep/30 px-6 py-20 text-center">
              <Shield size={40} className="mb-4 text-emerald/30" />
              <p className="font-display text-lg font-semibold text-ink">
                Build your squad
              </p>
              <p className="mt-1 max-w-xs text-sm text-ink-tertiary">
                Add players from the list below to see them on the pitch.
              </p>
            </div>
          )}

          {/* Player browser */}
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-ink-tertiary">
            Available Players
          </h2>
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="flex-1 max-w-sm">
              <SearchInput value={query} onChange={setQuery} placeholder="Search players to add…" />
            </div>
            <Dropdown label="Position" options={posOptions} value={posFilter} onChange={setPosFilter} />
          </div>

          {loading && (
            <div className="flex flex-col gap-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-14 w-full rounded-xl" />
              ))}
            </div>
          )}

          {!loading && error && <ErrorState message={error} onRetry={refetch} />}

          {!loading && !error && filtered.length === 0 && (
            <EmptyState title="No players match your search" />
          )}

          {!loading && !error && filtered.length > 0 && (
            <ul className="flex flex-col gap-1.5">
              {filtered.map((p) => (
                <PlayerBrowserRow
                  key={p.element ?? p.name}
                  player={p}
                  selected={squadState.isInSquad(p)}
                  disabled={!squadState.isInSquad(p) && squadState.isFull}
                  onToggle={() => squadState.toggle(p)}
                />
              ))}
            </ul>
          )}
        </div>

        {/* Squad list sidebar */}
        <aside className="h-fit rounded-xl border border-border-soft bg-surface p-4 lg:sticky lg:top-20">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
              <Users size={15} className="text-emerald" />
              Your Squad
            </h2>
            <Badge tone={squadState.isFull ? "teal" : "neutral"}>
              {squadState.squad.length}/{squadState.maxSize}
            </Badge>
          </div>

          {squadState.squad.length === 0 ? (
            <EmptyState title="No players selected" description="Add players from the list to build your squad." />
          ) : (
            <div className="flex flex-col gap-1">
              {squadState.squad.map((p) => {
                const isCaptain = captain === p;
                return (
                  <motion.div
                    key={p.element ?? p.name}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-surface-hover"
                  >
                    <PlayerAvatar name={p.name} photoUrl={p.photo_url} size="sm" />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1 truncate text-xs font-medium text-ink">
                        {p.name ?? "N/A"}
                        {isCaptain && (
                          <Crown size={10} className="shrink-0 text-gold" />
                        )}
                      </div>
                      <div className="flex items-center gap-1">
                        <TeamBadge team={p.team} logoUrl={p.team_logo_url} size="sm" />
                        {p.position && (
                          <span className="text-[9px] text-ink-tertiary">{p.position}</span>
                        )}
                      </div>
                    </div>
                    <span className="numeral text-xs font-semibold text-gold">
                      {formatStat(p.predicted_total_points)}
                    </span>
                    <button
                      onClick={() => squadState.removePlayer(p)}
                      aria-label={`Remove ${p.name ?? "player"}`}
                      className="shrink-0 rounded-md p-1 text-ink-tertiary hover:bg-coral/10 hover:text-coral"
                    >
                      <Trash2 size={13} />
                    </button>
                  </motion.div>
                );
              })}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

function PlayerBrowserRow({
  player,
  selected,
  disabled,
  onToggle,
}: {
  player: PlayerRecord;
  selected: boolean;
  disabled: boolean;
  onToggle: () => void;
}) {
  return (
    <li
      className={`flex items-center gap-3 rounded-lg border px-3 py-2.5 transition-colors ${
        selected
          ? "border-emerald/20 bg-emerald/[0.04]"
          : "border-border-soft bg-surface hover:bg-surface-hover"
      }`}
    >
      <PlayerAvatar name={player.name} photoUrl={player.photo_url} size="sm" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium text-ink">{player.name ?? "N/A"}</span>
          {player.position && (
            <span className="rounded bg-white/5 px-1 py-0.5 text-[9px] font-semibold uppercase text-ink-tertiary">
              {player.position}
            </span>
          )}
        </div>
        <div className="mt-1 flex items-center gap-2">
          <TeamBadge team={player.team} logoUrl={player.team_logo_url} size="sm" showName />
          <UpcomingFixtures player={player} variant="inline" maxFixtures={3} className="hidden md:inline-flex" />
        </div>
      </div>
      <span className="numeral hidden text-sm text-ink-secondary sm:block">{formatPrice(player.value)}</span>
      <span className="numeral text-sm font-semibold text-gold">{formatStat(player.predicted_total_points)}</span>
      <Button
        variant={selected ? "secondary" : "primary"}
        size="sm"
        disabled={disabled}
        onClick={onToggle}
        className="shrink-0"
      >
        {selected ? <Trash2 size={13} /> : <Plus size={13} />}
        <span className="hidden sm:inline">{selected ? "Remove" : "Add"}</span>
      </Button>
    </li>
  );
}
