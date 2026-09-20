import { Info } from "lucide-react";
import type { ConfidenceLevel } from "@/lib/insights";
import { Tooltip } from "@/components/ui/Tooltip";
import { cn } from "@/lib/utils";

interface ConfidenceBadgeProps {
  level: ConfidenceLevel;
  size?: "sm" | "md";
  showTooltip?: boolean;
  className?: string;
}

const CONFIDENCE_CONFIG: Record<
  ConfidenceLevel,
  { label: string; dot: string; bg: string; text: string; border: string }
> = {
  HIGH: {
    label: "High",
    dot: "bg-emerald-500",
    bg: "bg-emerald-50",
    text: "text-emerald-700",
    border: "border-emerald-200",
  },
  MEDIUM: {
    label: "Medium",
    dot: "bg-amber-500",
    bg: "bg-amber-50",
    text: "text-amber-700",
    border: "border-amber-200",
  },
  LOW: {
    label: "Low",
    dot: "bg-slate-400",
    bg: "bg-slate-50",
    text: "text-slate-600",
    border: "border-slate-200",
  },
};

const TOOLTIP_TEXT =
  "Prediction confidence reflects the strength and consistency of the available signals. It does not guarantee the player's actual score.";

/**
 * Human-readable confidence badge: HIGH / MEDIUM / LOW.
 * Includes both color AND text label for accessibility.
 * Optional tooltip explains what confidence means.
 */
export function ConfidenceBadge({
  level,
  size = "sm",
  showTooltip = true,
  className,
}: ConfidenceBadgeProps) {
  const config = CONFIDENCE_CONFIG[level];

  const badge = (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-black uppercase tracking-wider",
        config.bg,
        config.text,
        config.border,
        size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-3 py-1 text-xs",
        className,
      )}
      aria-label={`Confidence: ${config.label}`}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", config.dot)} />
      {config.label}
      {showTooltip && <Info size={size === "sm" ? 10 : 12} className="opacity-50" />}
    </span>
  );

  if (showTooltip) {
    return <Tooltip content={TOOLTIP_TEXT}>{badge}</Tooltip>;
  }

  return badge;
}
