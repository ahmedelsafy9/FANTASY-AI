import { cn } from "@/lib/utils";

interface StatProps {
  label: string;
  value: string;
  tone?: "gold" | "signal" | "teal" | "coral";
  size?: "sm" | "md";
}

const TONE_TEXT: Record<string, string> = {
  gold: "text-gold",
  signal: "text-signal-bright",
  teal: "text-emerald",
  coral: "text-coral",
};

export function Stat({ label, value, tone, size = "sm" }: StatProps) {
  return (
    <div className="flex flex-col">
      <span
        className={cn(
          "font-medium uppercase tracking-wider text-ink-tertiary",
          size === "sm" ? "text-[9px]" : "text-[10px]",
        )}
      >
        {label}
      </span>
      <span
        className={cn(
          "numeral font-semibold",
          size === "sm" ? "text-sm" : "text-lg",
          tone ? TONE_TEXT[tone] : "text-ink",
        )}
      >
        {value}
      </span>
    </div>
  );
}

interface ConfidenceBarProps {
  value: number | null;
  label?: string;
}

/**
 * A playing-time reliability proxy bar — NOT a true ML confidence score.
 * When the value is null (no data), shows a "not enough data" message.
 */
export function ConfidenceBar({ value, label }: ConfidenceBarProps) {
  if (value === null) {
    return (
      <div className="flex flex-col gap-1">
        <span className="text-[9px] font-medium uppercase tracking-wider text-ink-tertiary">
          {label ?? "Playing-time reliability"}
        </span>
        <span className="text-xs text-ink-tertiary italic">Not enough data</span>
      </div>
    );
  }

  const pct = Math.max(0, Math.min(1, value)) * 100;

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <span className="text-[9px] font-medium uppercase tracking-wider text-ink-tertiary">
          {label ?? "Playing-time reliability"}
        </span>
        <span className="numeral text-xs font-semibold text-ink">{Math.round(pct)}%</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-700",
            pct >= 75 ? "bg-emerald" : pct >= 50 ? "bg-gold" : "bg-coral",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
