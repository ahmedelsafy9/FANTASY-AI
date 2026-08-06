import {
  TrendingUp,
  TrendingDown,
  Clock,
  Home,
  DollarSign,
  Battery,
  Zap,
  Shield,
} from "lucide-react";
import type { Insight } from "@/lib/insights";
import { cn } from "@/lib/utils";

const INSIGHT_ICONS: Record<string, typeof TrendingUp> = {
  "Favorable fixture": Shield,
  "Tough fixture": Shield,
  "Form improving": TrendingUp,
  "Form dipping": TrendingDown,
  "High expected minutes": Clock,
  "Limited recent minutes": Clock,
  "Home advantage": Home,
  "Price rising": DollarSign,
  "Price falling": DollarSign,
  "Well rested": Battery,
};

const TONE_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  gold: { bg: "bg-gold/10", text: "text-gold", border: "border-gold/20" },
  signal: { bg: "bg-signal/10", text: "text-signal-bright", border: "border-signal/20" },
  teal: { bg: "bg-emerald/10", text: "text-emerald", border: "border-emerald/20" },
  coral: { bg: "bg-coral/10", text: "text-coral", border: "border-coral/20" },
  neutral: { bg: "bg-white/5", text: "text-ink-secondary", border: "border-border-soft" },
};

interface InsightTagProps {
  insight: Insight;
  className?: string;
}

/**
 * A football-intelligence styled insight tag. Shows an icon + label
 * instead of a plain text badge, making insights feel like meaningful
 * scouting intelligence. Uses existing deriveInsights() data unchanged.
 */
export function InsightTag({ insight, className }: InsightTagProps) {
  const Icon = INSIGHT_ICONS[insight.label] ?? Zap;
  const style = TONE_STYLES[insight.tone] ?? TONE_STYLES.neutral;

  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium",
        style.bg,
        style.text,
        style.border,
        className,
      )}
    >
      <Icon size={13} className="shrink-0 opacity-80" />
      {insight.label}
    </div>
  );
}
