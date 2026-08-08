import { cn } from "@/lib/utils";

interface StatProps {
  label: string;
  value: string;
  tone?: "gold" | "signal" | "teal" | "coral";
  size?: "sm" | "md";
}

const TONE_TEXT: Record<string, string> = {
  gold: "text-amber-700 font-black",
  signal: "text-indigo-700 font-black",
  teal: "text-emerald-700 font-black",
  coral: "text-red-700 font-black",
};

export function Stat({ label, value, tone, size = "sm" }: StatProps) {
  return (
    <div className="flex flex-col">
      <span
        className={cn(
          "font-black uppercase tracking-wider text-slate-500",
          size === "sm" ? "text-[10px]" : "text-[11px]",
        )}
      >
        {label}
      </span>
      <span
        className={cn(
          "numeral font-black",
          size === "sm" ? "text-base sm:text-lg" : "text-xl sm:text-2xl",
          tone ? TONE_TEXT[tone] : "text-slate-900",
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

export function ConfidenceBar({ value, label }: ConfidenceBarProps) {
  if (value === null) {
    return (
      <div className="flex flex-col gap-1">
        <span className="text-[10px] font-black uppercase tracking-wider text-slate-500">
          {label ?? "Playing-time reliability"}
        </span>
        <span className="text-xs text-slate-500 italic font-bold">Not enough data</span>
      </div>
    );
  }

  const pct = Math.max(0, Math.min(1, value)) * 100;

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-black uppercase tracking-wider text-slate-500">
          {label ?? "Playing-time reliability"}
        </span>
        <span className="numeral text-xs font-black text-slate-900">{Math.round(pct)}%</span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-200 shadow-inner">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-700",
            pct >= 75 ? "bg-emerald-600" : pct >= 50 ? "bg-amber-500" : "bg-red-500",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
