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
  gold: { bg: "bg-[#FDF8EC]", text: "text-[#8C680E]", border: "border-[#E5D08E]" },
  signal: { bg: "bg-[#EEE7FA]", text: "text-[#452477]", border: "border-[#D4C3ED]" },
  teal: { bg: "bg-[#EEF7FC]", text: "text-[#1E4D6B]", border: "border-[#B9DDF5]" },
  coral: { bg: "bg-[#FDECEC]", text: "text-[#991B1B]", border: "border-[#FCA5A5]" },
  neutral: { bg: "bg-[#F4F3F6]", text: "text-[#19171D]", border: "border-[#E8E3ED]" },
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
