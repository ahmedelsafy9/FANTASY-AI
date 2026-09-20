import { Tooltip } from "@/components/ui/Tooltip";
import { formatExpectedPointsNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

interface ExpectedPointsProps {
  points: number | null | undefined;
  size?: "sm" | "md" | "lg" | "xl";
  className?: string;
  showLabel?: boolean;
}

const SIZE_MAP = {
  sm: { number: "text-lg", label: "text-[9px]", suffix: "text-xs" },
  md: { number: "text-2xl", label: "text-[10px]", suffix: "text-sm" },
  lg: { number: "text-4xl sm:text-5xl", label: "text-[11px]", suffix: "text-base" },
  xl: { number: "text-5xl sm:text-7xl", label: "text-xs", suffix: "text-lg" },
};

const TOOLTIP_TEXT =
  "What we expect this player to score next Gameweek based on our analysis. This is a prediction, not a guarantee.";

/**
 * Prominent expected points display.
 * Shows "Expected: X.X pts" — the most important prediction number.
 * Uses warm amber tones to indicate prediction status.
 */
export function ExpectedPoints({
  points,
  size = "md",
  className,
  showLabel = true,
}: ExpectedPointsProps) {
  const value = typeof points === "number" ? points : null;
  const formatted = formatExpectedPointsNumber(points);
  const sizes = SIZE_MAP[size];

  const content = (
    <div className={cn("flex flex-col", className)}>
      {showLabel && (
        <span
          className={cn(
            "font-black uppercase tracking-widest text-[#92400E]",
            sizes.label,
          )}
        >
          Expected
        </span>
      )}
      <div className="flex items-baseline gap-1">
        <span
          className={cn(
            "numeral font-black leading-none",
            value !== null && value >= 7 ? "text-[#B45309]" : "text-[#92400E]",
            sizes.number,
          )}
        >
          {formatted}
        </span>
        <span
          className={cn(
            "font-bold text-[#B45309]/70",
            sizes.suffix,
          )}
        >
          pts
        </span>
      </div>
    </div>
  );

  if (showLabel) {
    return <Tooltip content={TOOLTIP_TEXT}>{content}</Tooltip>;
  }

  return content;
}
