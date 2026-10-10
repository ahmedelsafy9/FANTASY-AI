import { cn } from "@/lib/utils";

interface FDRBadgeProps {
  difficulty: number | null | undefined;
  size?: "sm" | "md";
  showLabel?: boolean;
  className?: string;
}

const FDR_COLORS: Record<number, { bg: string; text: string; border: string; label: string }> = {
  1: { bg: "bg-[#EDF6FC]", text: "text-[#1E4D6B]", border: "border-[#B9DDF5]", label: "Very Easy" },
  2: { bg: "bg-[#EEE7FA]", text: "text-[#452477]", border: "border-[#D5C6F0]", label: "Easy" },
  3: { bg: "bg-[#FDF8EC]", text: "text-[#8C680E]", border: "border-[#E5D08E]", label: "Medium" },
  4: { bg: "bg-[#FFF1ED]", text: "text-[#C2410C]", border: "border-[#FFDDD2]", label: "Hard" },
  5: { bg: "bg-[#FEF2F2]", text: "text-[#991B1B]", border: "border-[#FECACA]", label: "Very Hard" },
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
