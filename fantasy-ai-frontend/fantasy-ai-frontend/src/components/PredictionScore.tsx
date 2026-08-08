import { formatStat } from "@/lib/format";
import { cn } from "@/lib/utils";

interface PredictionScoreProps {
  points: number | null | undefined;
  size?: "sm" | "md" | "lg" | "xl";
  className?: string;
}

const SIZE_MAP = {
  sm: "text-xl",
  md: "text-3xl",
  lg: "text-5xl",
  xl: "text-7xl",
};

export function PredictionScore({ points, size = "md", className }: PredictionScoreProps) {
  const value = typeof points === "number" ? points : null;
  const isHigh = value !== null && value >= 7;
  const formatted = formatStat(points);

  return (
    <div className={cn("flex flex-col", className)}>
      <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">
        Expected Pts
      </span>
      <span
        className={cn(
          "numeral font-black leading-none text-amber-600",
          SIZE_MAP[size],
          isHigh && "text-amber-700",
        )}
      >
        {formatted}
      </span>
    </div>
  );
}
