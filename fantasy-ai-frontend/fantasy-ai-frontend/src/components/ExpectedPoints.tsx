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
  sm: {
    container: "px-2 py-1",
    number: "text-base font-black",
    label: "text-[8px]",
    unit: "text-[10px]",
  },
  md: {
    container: "px-3 py-1.5",
    number: "text-2xl font-black",
    label: "text-[9px]",
    unit: "text-xs",
  },
  lg: {
    container: "px-4 py-2.5",
    number: "text-4xl sm:text-5xl font-black",
    label: "text-[10px]",
    unit: "text-sm",
  },
  xl: {
    container: "px-6 py-4",
    number: "text-5xl sm:text-7xl font-black",
    label: "text-xs",
    unit: "text-base",
  },
};

const TOOLTIP_TEXT =
  "Projected points for the upcoming Gameweek derived from ML form, minute likelihood, and opponent difficulty. Whole number display.";

/**
 * Prominent expected points display.
 * Displays predicted-point values strictly as whole numbers (rounded for display).
 * Never mutates the underlying data.
 */
export function ExpectedPoints({
  points,
  size = "md",
  className,
  showLabel = true,
}: ExpectedPointsProps) {
  const value = typeof points === "number" && !Number.isNaN(points) ? points : null;
  const wholeNumber = formatExpectedPointsNumber(value);
  const dims = SIZE_MAP[size];

  const isElite = value !== null && Math.round(value) >= 7;

  const content = (
    <div
      className={cn(
        "flex flex-col items-end text-right rounded-xl transition-transform",
        className,
      )}
    >
      {showLabel && (
        <span
          className={cn(
            "font-black uppercase tracking-wider",
            isElite ? "text-gold-muted" : "text-ink-secondary",
            dims.label,
          )}
        >
          Predicted
        </span>
      )}
      <div className="flex items-baseline gap-1">
        <span
          className={cn(
            "numeral leading-none",
            isElite ? "text-gradient-gold drop-shadow-xs" : "text-stadium-deep",
            dims.number,
          )}
        >
          {wholeNumber}
        </span>
        <span
          className={cn(
            "font-bold uppercase tracking-wider",
            isElite ? "text-gold-muted" : "text-ink-secondary",
            dims.unit,
          )}
        >
          pts
        </span>
      </div>
    </div>
  );

  return <Tooltip content={TOOLTIP_TEXT}>{content}</Tooltip>;
}
