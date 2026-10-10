import { formatInt } from "@/lib/format";
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
  const formatted = formatInt(points);

  return (
    <div className={cn("flex flex-col", className)}>
      <span className="text-[10px] font-black uppercase tracking-widest text-[#6F6A76]">
        Expected Pts
      </span>
      <span
        className={cn(
          "numeral font-black leading-none",
          SIZE_MAP[size],
          isHigh ? "text-[#8C680E]" : "text-[#452477]",
        )}
      >
        {formatted}
      </span>
    </div>
  );
}
