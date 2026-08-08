import { cn } from "@/lib/utils";

interface FDRBadgeProps {
  difficulty: number | null | undefined;
  size?: "sm" | "md";
  showLabel?: boolean;
  className?: string;
}

const FDR_COLORS: Record<number, { bg: string; text: string; border: string; label: string }> = {
  1: { bg: "bg-emerald-100", text: "text-emerald-950", border: "border-emerald-300", label: "Very Easy" },
  2: { bg: "bg-emerald-100", text: "text-emerald-950", border: "border-emerald-300", label: "Easy" },
  3: { bg: "bg-amber-100", text: "text-amber-950", border: "border-amber-300", label: "Medium" },
  4: { bg: "bg-orange-100", text: "text-orange-950", border: "border-orange-300", label: "Hard" },
  5: { bg: "bg-red-100", text: "text-red-950", border: "border-red-300", label: "Very Hard" },
};

export function FDRBadge({ difficulty, size = "sm", showLabel = false, className }: FDRBadgeProps) {
  if (difficulty === null || difficulty === undefined) {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border border-slate-300 bg-slate-100 font-mono font-black text-slate-700",
          size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs",
          className,
        )}
      >
        FDR N/A
      </span>
    );
  }

  const clamped = Math.max(1, Math.min(5, Math.round(difficulty)));
  const scheme = FDR_COLORS[clamped] ?? FDR_COLORS[3];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-mono font-black shadow-sm",
        scheme.bg,
        scheme.text,
        scheme.border,
        size === "sm"
          ? "px-2 py-0.5 text-[10px]"
          : "px-2.5 py-1 text-xs",
        className,
      )}
      title={`Fixture Difficulty: ${clamped} — ${scheme.label}`}
    >
      FDR {clamped}
      {showLabel && <span className="font-bold opacity-90">· {scheme.label}</span>}
    </span>
  );
}
