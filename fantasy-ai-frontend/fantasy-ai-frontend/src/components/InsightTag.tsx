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
  gold: { bg: "bg-amber-100", text: "text-amber-950", border: "border-amber-300" },
  signal: { bg: "bg-indigo-100", text: "text-indigo-950", border: "border-indigo-300" },
  teal: { bg: "bg-emerald-100", text: "text-emerald-950", border: "border-emerald-300" },
  coral: { bg: "bg-red-100", text: "text-red-950", border: "border-red-300" },
  neutral: { bg: "bg-slate-100", text: "text-slate-900", border: "border-slate-300" },
};

interface InsightTagProps {
  insight: Insight;
  className?: string;
}

export function InsightTag({ insight, className }: InsightTagProps) {
  const Icon = INSIGHT_ICONS[insight.label] ?? Zap;
  const style = TONE_STYLES[insight.tone] ?? TONE_STYLES.neutral;

  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-black shadow-sm",
        style.bg,
        style.text,
        style.border,
        className,
      )}
    >
      <Icon size={13} className="shrink-0" />
      {insight.label}
    </div>
  );
}
