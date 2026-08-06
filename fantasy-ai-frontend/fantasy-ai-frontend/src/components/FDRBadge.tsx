import { cn } from "@/lib/utils";

interface FDRBadgeProps {
  difficulty: number | null | undefined;
  size?: "sm" | "md";
  showLabel?: boolean;
  className?: string;
}

const FDR_COLORS: Record<number, { bg: string; text: string; label: string }> = {
  1: { bg: "bg-fdr-1/15", text: "text-fdr-1", label: "Very Easy" },
  2: { bg: "bg-fdr-2/15", text: "text-fdr-2", label: "Easy" },
  3: { bg: "bg-fdr-3/15", text: "text-fdr-3", label: "Medium" },
  4: { bg: "bg-fdr-4/15", text: "text-fdr-4", label: "Hard" },
  5: { bg: "bg-fdr-5/15", text: "text-fdr-5", label: "Very Hard" },
};

/**
 * Fixture Difficulty Rating badge — a compact visual indicator showing
 * how tough the upcoming opponent is. Uses a 5-tier color scale from
 * green (easy) through gold (medium) to red (hard). Renders "N/A"
 * when the backend didn't provide fixture_difficulty.
 */
export function FDRBadge({ difficulty, size = "sm", showLabel = false, className }: FDRBadgeProps) {
  if (difficulty === null || difficulty === undefined) {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-md border border-border-soft bg-white/5 font-mono text-ink-tertiary",
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
        "inline-flex items-center gap-1.5 rounded-md border font-mono font-semibold",
        scheme.bg,
        scheme.text,
        size === "sm"
          ? "border-transparent px-2 py-0.5 text-[10px]"
          : "border-transparent px-2.5 py-1 text-xs",
        className,
      )}
      title={`Fixture Difficulty: ${clamped} — ${scheme.label}`}
    >
      FDR {clamped}
      {showLabel && <span className="font-normal opacity-80">· {scheme.label}</span>}
    </span>
  );
}
