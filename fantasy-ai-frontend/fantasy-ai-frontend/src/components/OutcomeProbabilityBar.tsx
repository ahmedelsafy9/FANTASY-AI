import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface OutcomeProbabilityBarProps {
  homeTeam: string;
  awayTeam: string;
  homeProb: number;
  drawProb: number;
  awayProb: number;
  predictedResult?: string;
  className?: string;
  animate?: boolean;
}

export function OutcomeProbabilityBar({
  homeTeam,
  awayTeam,
  homeProb,
  drawProb,
  awayProb,
  predictedResult,
  className,
  animate = true,
}: OutcomeProbabilityBarProps) {
  // Ensure valid numerical probabilities
  const hRaw = typeof homeProb === "number" && !Number.isNaN(homeProb) ? homeProb : 0.333;
  const dRaw = typeof drawProb === "number" && !Number.isNaN(drawProb) ? drawProb : 0.334;
  const aRaw = typeof awayProb === "number" && !Number.isNaN(awayProb) ? awayProb : 0.333;

  // If backend returns decimals 0.0 - 1.0, convert to %
  const hVal = hRaw <= 1.0 ? hRaw * 100 : hRaw;
  const dVal = dRaw <= 1.0 ? dRaw * 100 : dRaw;
  const aVal = aRaw <= 1.0 ? aRaw * 100 : aRaw;

  // Round for whole-number display
  let hPct = Math.round(hVal);
  let dPct = Math.round(dVal);
  let aPct = Math.round(aVal);

  // Normalize display sum to 100% if rounding creates 99% or 101%
  const sum = hPct + dPct + aPct;
  if (sum !== 100 && sum > 0) {
    const diff = 100 - sum;
    // Add diff to largest probability
    if (hPct >= dPct && hPct >= aPct) hPct += diff;
    else if (aPct >= hPct && aPct >= dPct) aPct += diff;
    else dPct += diff;
  }

  const isHomeWinner = predictedResult === "HOME_WIN";
  const isDrawWinner = predictedResult === "DRAW";
  const isAwayWinner = predictedResult === "AWAY_WIN";

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      {/* 3 Outcome Dominant Display Cards */}
      <div className="grid grid-cols-3 gap-2">
        {/* Home Win */}
        <div
          className={cn(
            "flex flex-col items-center justify-center rounded-xl p-2.5 text-center border transition-all",
            isHomeWinner
              ? "bg-stadium-deep text-ivory-surface border-gold-metallic/60 shadow-md ring-1 ring-gold-metallic/40"
              : "bg-ivory-subtle text-ink-primary border-border",
          )}
        >
          <span
            className={cn(
              "text-[10px] font-black uppercase tracking-wider truncate max-w-full px-1",
              isHomeWinner ? "text-gold-bright" : "text-ink-secondary",
            )}
          >
            {homeTeam}
          </span>
          <div className="flex items-baseline gap-0.5 mt-0.5">
            <span
              className={cn(
                "numeral text-xl sm:text-2xl font-black leading-none",
                isHomeWinner ? "text-ivory-surface" : "text-stadium-deep",
              )}
            >
              {hPct}
            </span>
            <span
              className={cn(
                "text-xs font-bold",
                isHomeWinner ? "text-gold-bright" : "text-ink-secondary",
              )}
            >
              %
            </span>
          </div>
          <span
            className={cn(
              "text-[9px] font-bold uppercase tracking-wider mt-0.5",
              isHomeWinner ? "text-ivory-surface/80" : "text-ink-secondary",
            )}
          >
            Home Win
          </span>
        </div>

        {/* Draw */}
        <div
          className={cn(
            "flex flex-col items-center justify-center rounded-xl p-2.5 text-center border transition-all",
            isDrawWinner
              ? "bg-[#253E32] text-ivory-surface border-gold-metallic/60 shadow-md ring-1 ring-gold-metallic/40"
              : "bg-ivory-subtle text-ink-primary border-border",
          )}
        >
          <span
            className={cn(
              "text-[10px] font-black uppercase tracking-wider",
              isDrawWinner ? "text-gold-bright" : "text-ink-secondary",
            )}
          >
            DRAW
          </span>
          <div className="flex items-baseline gap-0.5 mt-0.5">
            <span
              className={cn(
                "numeral text-xl sm:text-2xl font-black leading-none",
                isDrawWinner ? "text-gold-bright" : "text-gold-dark",
              )}
            >
              {dPct}
            </span>
            <span
              className={cn(
                "text-xs font-bold",
                isDrawWinner ? "text-gold-bright" : "text-gold-dark",
              )}
            >
              %
            </span>
          </div>
          <span
            className={cn(
              "text-[9px] font-bold uppercase tracking-wider mt-0.5",
              isDrawWinner ? "text-ivory-surface/80" : "text-ink-secondary",
            )}
          >
            Level
          </span>
        </div>

        {/* Away Win */}
        <div
          className={cn(
            "flex flex-col items-center justify-center rounded-xl p-2.5 text-center border transition-all",
            isAwayWinner
              ? "bg-stadium-deep text-ivory-surface border-gold-metallic/60 shadow-md ring-1 ring-gold-metallic/40"
              : "bg-ivory-subtle text-ink-primary border-border",
          )}
        >
          <span
            className={cn(
              "text-[10px] font-black uppercase tracking-wider truncate max-w-full px-1",
              isAwayWinner ? "text-gold-bright" : "text-ink-secondary",
            )}
          >
            {awayTeam}
          </span>
          <div className="flex items-baseline gap-0.5 mt-0.5">
            <span
              className={cn(
                "numeral text-xl sm:text-2xl font-black leading-none",
                isAwayWinner ? "text-ivory-surface" : "text-stadium-forest",
              )}
            >
              {aPct}
            </span>
            <span
              className={cn(
                "text-xs font-bold",
                isAwayWinner ? "text-gold-bright" : "text-ink-secondary",
              )}
            >
              %
            </span>
          </div>
          <span
            className={cn(
              "text-[9px] font-bold uppercase tracking-wider mt-0.5",
              isAwayWinner ? "text-ivory-surface/80" : "text-ink-secondary",
            )}
          >
            Away Win
          </span>
        </div>
      </div>

      {/* Continuous Segmented Probability Bar */}
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-ivory-subtle p-0.5 border border-border shadow-inner">
        {animate ? (
          <>
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${hPct}%` }}
              transition={{ duration: 0.6, ease: "easeOut" }}
              className="h-full rounded-l-full bg-stadium-deep transition-all"
              title={`Home Win: ${hPct}%`}
            />
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${dPct}%` }}
              transition={{ duration: 0.6, delay: 0.1, ease: "easeOut" }}
              className="h-full bg-gold-metallic transition-all"
              title={`Draw: ${dPct}%`}
            />
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${aPct}%` }}
              transition={{ duration: 0.6, delay: 0.2, ease: "easeOut" }}
              className="h-full rounded-r-full bg-stadium-forest transition-all"
              title={`Away Win: ${aPct}%`}
            />
          </>
        ) : (
          <>
            <div
              style={{ width: `${hPct}%` }}
              className="h-full rounded-l-full bg-stadium-deep"
              title={`Home Win: ${hPct}%`}
            />
            <div
              style={{ width: `${dPct}%` }}
              className="h-full bg-gold-metallic"
              title={`Draw: ${dPct}%`}
            />
            <div
              style={{ width: `${aPct}%` }}
              className="h-full rounded-r-full bg-stadium-forest"
              title={`Away Win: ${aPct}%`}
            />
          </>
        )}
      </div>
    </div>
  );
}
