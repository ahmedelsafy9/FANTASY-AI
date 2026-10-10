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
      <h4 className="text-xs font-black uppercase tracking-wider text-[#6F6A76]">
        {title}
      </h4>
      <div className="flex flex-col gap-1.5">
        {reasons.map((reason, i) => (
          <div
            key={i}
            className="flex items-center gap-2.5 rounded-xl bg-[#F8F7FA] border border-[#E8E3ED] px-3.5 py-2.5 text-xs sm:text-sm font-semibold text-[#19171D] shadow-xs"
          >
            <span className="text-base leading-none shrink-0">{reason.icon}</span>
            <span>{reason.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
