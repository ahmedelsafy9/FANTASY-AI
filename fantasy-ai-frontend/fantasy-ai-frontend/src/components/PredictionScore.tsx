import { formatStat } from "@/lib/format";
import { cn } from "@/lib/utils";

interface PredictionScoreProps {
  points: number | null | undefined;
  size?: "sm" | "md" | "lg" | "xl";
  className?: string;
}

const SIZE_MAP = {
  sm: "text-lg",
  md: "text-3xl",
  lg: "text-5xl",
  xl: "text-7xl",
};

/**
 * Standalone predicted points display — the signature numeral of
 * Fantasy-AI. Large gold monospace number with "xPts" label.
 * Optional glow effect for high-value predictions (>7.0).
 */
export function PredictionScore({ points, size = "md", className }: PredictionScoreProps) {
  const value = typeof points === "number" ? points : null;
  const isHigh = value !== null && value >= 7;
  const formatted = formatStat(points);

  return (
    <div className={cn("flex flex-col", className)}>
      <span className="text-[10px] font-medium uppercase tracking-widest text-ink-tertiary">
        Expected Pts
      </span>
      <span
        className={cn(
          "numeral text-gradient-gold font-bold leading-none",
          SIZE_MAP[size],
          isHigh && "drop-shadow-[0_0_20px_rgba(232,184,92,0.3)]",
        )}
      >
        {formatted}
      </span>
    </div>
  );
}
