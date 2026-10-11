import { cn } from "@/lib/utils";

interface FDRBadgeProps {
  difficulty: number | null | undefined;
  size?: "sm" | "md";
  showLabel?: boolean;
  className?: string;
}

const FDR_COLORS: Record<number, { bg: string; text: string; border: string; label: string }> = {
  1: { bg: "bg-emerald-50", text: "text-emerald-900", border: "border-emerald-200", label: "Favorable" },
  2: { bg: "bg-emerald-50/80", text: "text-emerald-800", border: "border-emerald-200", label: "Good" },
  3: { bg: "bg-[#FDF8EC]", text: "text-[#8C680E]", border: "border-[#E5D08E]", label: "Neutral" },
  4: { bg: "bg-orange-50", text: "text-orange-900", border: "border-orange-200", label: "Tough" },
  5: { bg: "bg-rose-50", text: "text-rose-900", border: "border-rose-200", label: "Severe" },
};

export function FDRBadge({ difficulty, size = "sm", showLabel = false, className }: FDRBadgeProps) {
  if (difficulty === null || difficulty === undefined || Number.isNaN(difficulty)) {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1 rounded-full border border-border bg-ivory-subtle font-mono font-bold text-ink-secondary",
          size === "sm" ? "px-1.5 py-0.5 text-[9px]" : "px-2 py-0.5 text-[10px]",
          className,
        )}
      >
        FDR —
      </span>
    );
  }

  const clamped = Math.max(1, Math.min(5, Math.round(difficulty)));
  const scheme = FDR_COLORS[clamped] ?? FDR_COLORS[3];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border font-mono font-black shadow-xs select-none",
        scheme.bg,
        scheme.text,
        scheme.border,
        size === "sm" ? "px-1.5 py-0.5 text-[9px]" : "px-2 py-0.5 text-[10px]",
        className,
      )}
      title={`Fixture Difficulty: ${clamped} (${scheme.label})`}
    >
      <span>FDR {clamped}</span>
      {showLabel && <span className="font-semibold opacity-85">· {scheme.label}</span>}
    </span>
  );
}
