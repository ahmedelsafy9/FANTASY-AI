import { CalendarClock } from "lucide-react";

interface GameweekBadgeProps {
  gameweek: number | null | undefined;
}

/**
 * The backend does not expose a deadline timestamp anywhere in its
 * responses (confirmed by inspecting every schema), so this deliberately
 * does NOT render a countdown — inventing one would violate the "no fake
 * data" requirement. It shows only the real `predicted_for_gw` value.
 */
export function GameweekBadge({ gameweek }: GameweekBadgeProps) {
  return (
    <div className="glass inline-flex items-center gap-3 rounded-2xl border border-border-medium px-5 py-3">
      <CalendarClock size={18} className="text-signal" aria-hidden="true" />
      <div>
        <div className="text-[11px] uppercase tracking-wide text-ink-tertiary">
          Upcoming Gameweek
        </div>
        <div className="numeral text-xl font-bold text-ink">
          {typeof gameweek === "number" ? `GW ${gameweek}` : "N/A"}
        </div>
      </div>
    </div>
  );
}
