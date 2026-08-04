import { cn } from "@/lib/utils";

interface StatProps {
  label: string;
  value: string;
  tone?: "default" | "gold" | "signal" | "teal" | "coral";
  size?: "sm" | "md" | "lg";
}

const TONE_CLASSES: Record<string, string> = {
  default: "text-ink",
  gold: "text-gold",
  signal: "text-signal-bright",
  teal: "text-teal",
  coral: "text-coral",
};

const SIZE_CLASSES: Record<string, string> = {
  sm: "text-base",
  md: "text-2xl",
  lg: "text-5xl",
};

/** A labeled numeral in the app's signature monospace "data readout" style. */
export function Stat({ label, value, tone = "default", size = "sm" }: StatProps) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] uppercase tracking-wide text-ink-tertiary">{label}</span>
      <span className={cn("numeral font-semibold leading-none", TONE_CLASSES[tone], SIZE_CLASSES[size])}>
        {value}
      </span>
    </div>
  );
}

interface ConfidenceBarProps {
  /** 0-1 fraction. If null/undefined, renders an honest "not available" state. */
  value: number | null | undefined;
  label?: string;
}

/**
 * A thin gradient readout bar — the app's recurring signature element.
 * The backend does not expose an explicit "confidence" score; when a
 * meaningful, real signal (e.g. a derived form ratio) is passed in, this
 * renders it. When nothing real is available, it renders an honest
 * "not available" state instead of fabricating a number.
 */
export function ConfidenceBar({ value, label }: ConfidenceBarProps) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return (
      <div className="flex items-center gap-2">
        <div className="h-1.5 flex-1 rounded-full bg-white/[0.06]" />
        <span className="text-[11px] text-ink-tertiary">N/A</span>
      </div>
    );
  }
  const pct = Math.max(0, Math.min(1, value)) * 100;
  const tone = pct >= 66 ? "HIGH" : pct >= 33 ? "MODERATE" : "LOW";
  const barColor = pct >= 66 ? "bg-teal" : pct >= 33 ? "bg-gold" : "bg-coral";

  return (
    <div className="flex flex-col gap-1.5">
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
        <div
          className={cn("h-full rounded-full transition-all duration-700 ease-out", barColor)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[11px] font-medium uppercase tracking-wide text-ink-tertiary">
        {label ?? `${tone} CONFIDENCE`}
      </span>
    </div>
  );
}
