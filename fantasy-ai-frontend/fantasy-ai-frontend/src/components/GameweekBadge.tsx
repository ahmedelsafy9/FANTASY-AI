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
    <div className="inline-flex items-center gap-3 rounded-xl border border-[#E8E3ED] bg-white px-4 py-2.5 shadow-sm">
      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#EEE7FA] text-[#7041C5]">
        <CalendarClock size={18} aria-hidden="true" />
      </div>
      <div>
        <div className="text-[10px] font-bold uppercase tracking-wider text-[#6F6A76]">
          Target Gameweek
        </div>
        <div className="numeral text-lg font-black text-[#19171D]">
          {typeof gameweek === "number" ? `GW ${gameweek}` : "N/A"}
        </div>
      </div>
    </div>
  );
}
