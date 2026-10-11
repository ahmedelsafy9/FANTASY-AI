import { Check, AlertTriangle, Activity, Ban, HelpCircle, XCircle } from "lucide-react";
import type { PlayerRecord } from "@/types/api";
import { derivePlayerAvailability, type AvailabilityInfo } from "@/lib/availability";
import { Tooltip } from "@/components/ui/Tooltip";
import { cn } from "@/lib/utils";

interface PlayerAvailabilityBadgeProps {
  player: PlayerRecord;
  size?: "sm" | "md";
  showIconOnly?: boolean;
  className?: string;
}

export function PlayerAvailabilityBadge({
  player,
  size = "sm",
  showIconOnly = false,
  className,
}: PlayerAvailabilityBadgeProps) {
  const info: AvailabilityInfo = derivePlayerAvailability(player);

  const config = {
    available: {
      bg: "bg-emerald-50 text-emerald-800 border-emerald-200/80",
      icon: Check,
      ariaLabel: "Player is fully fit and available",
    },
    doubtful: {
      bg: "bg-amber-50 text-amber-900 border-amber-300",
      icon: AlertTriangle,
      ariaLabel: info.chancePct ? `Player is doubtful (${info.chancePct}% chance of playing)` : "Player is doubtful",
    },
    injured: {
      bg: "bg-rose-50 text-rose-800 border-rose-200",
      icon: Activity,
      ariaLabel: "Player is currently injured",
    },
    suspended: {
      bg: "bg-red-100 text-red-900 border-red-300",
      icon: Ban,
      ariaLabel: "Player is suspended",
    },
    unavailable: {
      bg: "bg-stone-100 text-stone-700 border-stone-300",
      icon: XCircle,
      ariaLabel: "Player is unavailable",
    },
    unknown: {
      bg: "bg-ivory-subtle text-ink-secondary border-border",
      icon: HelpCircle,
      ariaLabel: "Player availability status is pending confirmation",
    },
  }[info.state];

  const Icon = config.icon;
  const isSm = size === "sm";

  const badgeContent = (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border font-bold uppercase tracking-wider select-none",
        isSm ? "px-2 py-0.5 text-[9px]" : "px-2.5 py-1 text-[10px]",
        config.bg,
        className,
      )}
      aria-label={config.ariaLabel}
    >
      <Icon className={isSm ? "h-2.5 w-2.5 shrink-0" : "h-3 w-3 shrink-0"} />
      {!showIconOnly && <span>{info.label}</span>}
    </span>
  );

  if (info.news) {
    return (
      <Tooltip content={`Official FPL Update: ${info.news}`}>
        {badgeContent}
      </Tooltip>
    );
  }

  return badgeContent;
}
