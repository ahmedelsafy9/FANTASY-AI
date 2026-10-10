import { Sparkles } from "lucide-react";

interface LowOwnershipBadgeProps {
  ownership?: unknown;
  predictedPoints?: unknown;
  showLabel?: boolean;
  className?: string;
}

/**
 * Evaluates whether a player qualifies as a subtle low-ownership high-potential gem.
 * Condition 1: Ownership <= 10.0%
 * Condition 2: Projected points >= 5.0 pts
 */
export function isLowOwnershipGem(
  ownership: unknown,
  predictedPoints: unknown,
  maxOwnership = 10.0,
  minPoints = 5.0
): boolean {
  if (ownership == null || predictedPoints == null) return false;
  const numOwn = typeof ownership === "number" ? ownership : parseFloat(String(ownership));
  const numPts = typeof predictedPoints === "number" ? predictedPoints : parseFloat(String(predictedPoints));
  if (Number.isNaN(numOwn) || Number.isNaN(numPts)) return false;
  return numOwn <= maxOwnership && numPts >= minPoints;
}

/**
 * Subtle visual badge for players with low ownership and strong projected returns.
 */
export function LowOwnershipBadge({
  ownership,
  predictedPoints,
  showLabel = true,
  className = "",
}: LowOwnershipBadgeProps) {
  if (!isLowOwnershipGem(ownership, predictedPoints)) {
    return null;
  }

  return (
    <span
      title="Low ownership (≤10%) with high projected returns (≥5 pts)"
      className={`inline-flex items-center gap-1 rounded-full border border-[#E5D08E] bg-[#FDF8EC] px-2 py-0.5 text-[10px] font-bold text-[#8C680E] shadow-sm transition-colors hover:bg-[#F9F0D6] ${className}`}
    >
      <Sparkles size={11} className="text-[#B58A18] shrink-0" />
      {showLabel && <span>Hidden Gem</span>}
    </span>
  );
}

export default LowOwnershipBadge;
