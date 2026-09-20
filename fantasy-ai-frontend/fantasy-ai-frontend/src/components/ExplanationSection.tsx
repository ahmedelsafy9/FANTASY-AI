import type { PlayerReason } from "@/lib/insights";
import { cn } from "@/lib/utils";

interface ExplanationSectionProps {
  reasons: PlayerReason[];
  title?: string;
  className?: string;
}

/**
 * "Why this player?" section showing 2-4 human-readable reasons
 * derived from real backend signals. Each reason has an icon and
 * short text. Never fabricates reasons.
 */
export function ExplanationSection({
  reasons,
  title = "Why this player?",
  className,
}: ExplanationSectionProps) {
  if (reasons.length === 0) return null;

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <h4 className="text-xs font-black uppercase tracking-wider text-[#64748B]">
        {title}
      </h4>
      <div className="flex flex-col gap-1.5">
        {reasons.map((reason, i) => (
          <div
            key={i}
            className="flex items-center gap-2.5 rounded-xl bg-[#F8FAFC] border border-[#F1F5F9] px-3 py-2 text-sm font-semibold text-[#334155]"
          >
            <span className="text-base leading-none shrink-0">{reason.icon}</span>
            <span>{reason.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
