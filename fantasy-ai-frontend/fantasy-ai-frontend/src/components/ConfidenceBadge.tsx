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
    dot: "bg-[#7041C5]",
    bg: "bg-[#EEE7FA]",
    text: "text-[#452477]",
    border: "border-[#D4C3ED]",
  },
  MEDIUM: {
    label: "Medium",
    dot: "bg-[#B58A18]",
    bg: "bg-[#FDF8EC]",
    text: "text-[#8C680E]",
    border: "border-[#E5D08E]",
  },
  LOW: {
    label: "Low",
    dot: "bg-[#9B95A3]",
    bg: "bg-[#F4F3F6]",
    text: "text-[#6F6A76]",
    border: "border-[#E8E3ED]",
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
