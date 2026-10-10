import { cn } from "@/lib/utils";

interface StatProps {
  label: string;
  value: string;
  tone?: "gold" | "signal" | "teal" | "coral";
  size?: "sm" | "md";
}

const TONE_TEXT: Record<string, string> = {
  gold: "text-[#8C680E] font-black",
  signal: "text-[#7041C5] font-black",
  teal: "text-[#246B9C] font-black",
  coral: "text-[#C2410C] font-black",
};

export function Stat({ label, value, tone, size = "sm" }: StatProps) {
  return (
    <div className="flex flex-col">
      <span
        className={cn(
          "font-black uppercase tracking-wider text-[#6F6A76]",
          size === "sm" ? "text-[10px]" : "text-[11px]",
        )}
      >
        {label}
      </span>
      <span
        className={cn(
          "numeral font-black",
          size === "sm" ? "text-base sm:text-lg" : "text-xl sm:text-2xl",
          tone ? TONE_TEXT[tone] : "text-[#19171D]",
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
        <span className="text-[10px] font-black uppercase tracking-wider text-[#6F6A76]">
          {label ?? "Playing-time reliability"}
        </span>
        <span className="text-xs text-[#6F6A76] italic font-bold">Not enough data</span>
      </div>
    );
  }

  const pct = Math.max(0, Math.min(1, value)) * 100;

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-black uppercase tracking-wider text-[#6F6A76]">
          {label ?? "Playing-time reliability"}
        </span>
        <span className="numeral text-xs font-black text-[#19171D]">{Math.round(pct)}%</span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-[#E8E3ED] shadow-inner">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-700",
            pct >= 75 ? "bg-[#7041C5]" : pct >= 50 ? "bg-[#B58A18]" : "bg-red-500",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
