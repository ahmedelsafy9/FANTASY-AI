import { motion } from "framer-motion";
import { ChevronRight } from "lucide-react";
import type { PlayerRecord } from "@/types/api";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { PlayerAvailabilityBadge } from "@/components/PlayerAvailabilityBadge";
import { UpcomingFixtures } from "@/components/UpcomingFixtures";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { LowOwnershipBadge } from "@/components/LowOwnershipBadge";
import { deriveConfidenceLevel } from "@/lib/insights";
import { formatStat } from "@/lib/format";
import { getPlayerPrice } from "@/hooks/useSquad";

interface PredictionTableProps {
  players: PlayerRecord[];
  onSelectPlayer: (player: PlayerRecord) => void;
}

export function PredictionTable({ players, onSelectPlayer }: PredictionTableProps) {
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-ivory-surface shadow-card">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm border-collapse">
          <thead>
            <tr className="border-b border-border bg-ivory-subtle text-[11px] font-black uppercase tracking-wider text-ink-secondary">
              <th className="py-3.5 pl-4 pr-2 text-center w-12">#</th>
              <th className="py-3.5 px-3 min-w-[180px]">Player</th>
              <th className="py-3.5 px-3">Status</th>
              <th className="py-3.5 px-3">Pos</th>
              <th className="py-3.5 px-3">Team</th>
              <th className="py-3.5 px-3 text-right">Price</th>
              <th className="py-3.5 px-3 text-right">
                <span className="text-gold-dark font-black">Predicted Pts</span>
              </th>
              <th className="py-3.5 px-3 text-center">Confidence</th>
              <th className="py-3.5 px-3 text-right">Form (3 GW)</th>
              <th className="py-3.5 px-3 min-w-[120px]">Next Fixture</th>
              <th className="py-3.5 pr-4 pl-2 text-right"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {players.map((p, idx) => {
              const price = getPlayerPrice(p);
              const expectedPoints = p.predicted_expected_points ?? p.predicted_total_points;
              const confidence = deriveConfidenceLevel(p);
              const isElite = typeof expectedPoints === "number" && Math.round(expectedPoints) >= 7;

              return (
                <motion.tr
                  key={p.element ?? p.name ?? idx}
                  onClick={() => onSelectPlayer(p)}
                  whileHover={{ backgroundColor: "#EFE8DA" }}
                  className="cursor-pointer transition-colors group"
                >
                  {/* Rank */}
                  <td className="py-3 pl-4 pr-2 text-center">
                    <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-ivory-subtle text-xs font-mono font-black text-ink-primary group-hover:bg-stadium-deep group-hover:text-ivory-surface transition-colors">
                      {idx + 1}
                    </span>
                  </td>

                  {/* Player info */}
                  <td className="py-3 px-3">
                    <div className="flex items-center gap-3">
                      <PlayerAvatar
                        name={p.name}
                        photoUrl={p.photo_url}
                        size="sm"
                        className="ring-1 ring-border"
                      />
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-display font-black text-ink-primary truncate group-hover:text-stadium-deep transition-colors">
                            {p.name ?? "N/A"}
                          </span>
                          <LowOwnershipBadge
                            ownership={p.selected_by_percent ?? (p as Record<string, unknown>).ownership_pct as number | undefined}
                            predictedPoints={expectedPoints}
                            showLabel={false}
                          />
                        </div>
                      </div>
                    </div>
                  </td>

                  {/* Availability Badge */}
                  <td className="py-3 px-3">
                    <PlayerAvailabilityBadge player={p} size="sm" />
                  </td>

                  {/* Position */}
                  <td className="py-3 px-3">
                    <span className="rounded-md bg-ivory-subtle border border-border px-2 py-0.5 font-mono text-[10px] font-black uppercase text-ink-primary">
                      {p.position === "GKP" ? "GK" : p.position ?? "-"}
                    </span>
                  </td>

                  {/* Team */}
                  <td className="py-3 px-3">
                    <TeamBadge team={p.team} logoUrl={p.team_logo_url} size="sm" showName />
                  </td>

                  {/* Price */}
                  <td className="py-3 px-3 text-right font-mono font-bold text-ink-primary">
                    £{price.toFixed(1)}m
                  </td>

                  {/* Predicted Points (Whole Number display) */}
                  <td className="py-3 px-3 text-right">
                    <span
                      className={`inline-block rounded-lg px-2.5 py-1 font-mono font-black border ${
                        isElite
                          ? "bg-gold-light text-gold-dark border-gold-border"
                          : "bg-ivory-subtle text-stadium-deep border-border"
                      }`}
                    >
                      {formatStat(expectedPoints)} pts
                    </span>
                  </td>

                  {/* Confidence */}
                  <td className="py-3 px-3 text-center">
                    <ConfidenceBadge level={confidence} showTooltip={false} />
                  </td>

                  {/* Form */}
                  <td className="py-3 px-3 text-right font-mono font-bold text-ink-secondary">
                    {typeof p.total_points_avg_last_3 === "number"
                      ? formatStat(p.total_points_avg_last_3)
                      : "—"}
                  </td>

                  {/* Upcoming fixture */}
                  <td className="py-3 px-3">
                    <UpcomingFixtures player={p} variant="compact" maxFixtures={1} />
                  </td>

                  {/* Arrow */}
                  <td className="py-3 pr-4 pl-2 text-right">
                    <ChevronRight size={16} className="text-ink-secondary group-hover:text-gold-metallic group-hover:translate-x-0.5 transition-all inline-block" />
                  </td>
                </motion.tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
