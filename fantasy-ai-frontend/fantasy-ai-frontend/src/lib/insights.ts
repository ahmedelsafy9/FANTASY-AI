import type { PlayerRecord } from "@/types/api";

export interface Insight {
  label: string;
  tone: "gold" | "signal" | "teal" | "coral" | "neutral";
}

/** Confidence level derived from real prediction signals. */
export type ConfidenceLevel = "HIGH" | "MEDIUM" | "LOW";

/** A human-readable reason for why a player is highlighted. */
export interface PlayerReason {
  icon: string;
  text: string;
}

/* ── Confidence derivation ─────────────────────────────────────────── */

/**
 * Derives a transparent, deterministic confidence level from REAL
 * backend data only. The mapping:
 *
 *   HIGH  — strong recent minutes (≥70 avg) AND multiple positive
 *           prediction signals or high haul probability (≥35%)
 *   MEDIUM — decent minutes (≥45 avg) AND some positive signals
 *            or moderate haul probability (≥20%)
 *   LOW   — everything else (limited data, rotation risk, etc.)
 *
 * This is NOT model accuracy. The tooltip must always clarify:
 * "Prediction confidence reflects the strength and consistency of
 *  the available signals. It does not guarantee the player's actual score."
 */
export function deriveConfidenceLevel(player: PlayerRecord): ConfidenceLevel {
  const minutes = player.minutes_avg_last_5 ?? player.minutes_avg_last_3;
  const p6 = player.prob_high_score_6;

  // Count positive prediction signals
  let positiveSignals = 0;
  const signals = player.prediction_signals;
  if (signals) {
    if (signals.recent_form?.rating === "Elite" || signals.recent_form?.rating === "Strong") positiveSignals++;
    if (signals.expected_minutes?.rating === "Starter" || signals.expected_minutes?.rating === "Nailed") positiveSignals++;
    if (signals.fixture_difficulty?.rating === "Easy" || signals.fixture_difficulty?.rating === "Favorable") positiveSignals++;
    if (signals.opportunity?.rating === "High" || signals.opportunity?.rating === "Elite") positiveSignals++;
    if (signals.attacking_threat?.rating === "High" || signals.attacking_threat?.rating === "Elite") positiveSignals++;
  }

  // Also count data-derived positives
  if (typeof player.total_points_avg_last_3 === "number" && player.total_points_avg_last_3 >= 5) positiveSignals++;
  if (typeof player.fixture_difficulty === "number" && player.fixture_difficulty <= 2) positiveSignals++;

  const hasHighMinutes = typeof minutes === "number" && minutes >= 70;
  const hasDecentMinutes = typeof minutes === "number" && minutes >= 45;
  const hasStrongSignals = positiveSignals >= 3 || (typeof p6 === "number" && p6 >= 0.35);
  const hasSomeSignals = positiveSignals >= 2 || (typeof p6 === "number" && p6 >= 0.20);

  if (hasHighMinutes && hasStrongSignals) return "HIGH";
  if (hasDecentMinutes && hasSomeSignals) return "MEDIUM";
  return "LOW";
}

/* ── Reason derivation ─────────────────────────────────────────────── */

/**
 * Generates 2-4 human-readable reasons for why this player stands out.
 * Every reason traces to a REAL backend field. No fabrication.
 * Returns empty array if insufficient data.
 */
export function deriveReasons(player: PlayerRecord): PlayerReason[] {
  const reasons: PlayerReason[] = [];

  // Goal threat from predicted goals or xG
  if (typeof player.predicted_goals === "number" && player.predicted_goals >= 0.25) {
    reasons.push({ icon: "⚽", text: "Strong goal threat" });
  } else if (typeof player.xG_avg_last_3 === "number" && player.xG_avg_last_3 >= 0.3) {
    reasons.push({ icon: "⚽", text: "Strong goal threat" });
  } else if (typeof player.xG_avg_last_3 === "number" && player.xG_avg_last_3 >= 0.15) {
    reasons.push({ icon: "⚽", text: "Goal potential" });
  }

  // Creative output from predicted assists or xA
  if (typeof player.predicted_assists === "number" && player.predicted_assists >= 0.2) {
    reasons.push({ icon: "🎯", text: "Good creative output" });
  } else if (typeof player.xA_avg_last_3 === "number" && player.xA_avg_last_3 >= 0.2) {
    reasons.push({ icon: "🎯", text: "Good creative output" });
  }

  // Clean sheet potential for DEF/GKP
  if (
    (player.position === "DEF" || player.position === "GKP") &&
    typeof (player.predicted_clean_sheet_prob ?? player.predicted_clean_sheet_probability) === "number"
  ) {
    const csProb = (player.predicted_clean_sheet_prob ?? player.predicted_clean_sheet_probability)!;
    if (csProb >= 0.35) {
      reasons.push({ icon: "🛡️", text: "Good clean sheet chance" });
    }
  }

  // Playing time signal
  const playProb = player.predicted_p_play_60 ?? player.predicted_minutes_60_probability;
  const minutesAvg = player.minutes_avg_last_5 ?? player.minutes_avg_last_3;
  if (typeof playProb === "number" && playProb >= 0.8) {
    reasons.push({ icon: "🟢", text: "Likely to start" });
  } else if (typeof minutesAvg === "number" && minutesAvg >= 75) {
    reasons.push({ icon: "🟢", text: "Consistent starter" });
  } else if (typeof minutesAvg === "number" && minutesAvg >= 45 && minutesAvg < 70) {
    reasons.push({ icon: "🟡", text: "Rotation risk" });
  } else if (typeof playProb === "number" && playProb < 0.5) {
    reasons.push({ icon: "🔴", text: "May not play" });
  }

  // Fixture difficulty
  if (typeof player.fixture_difficulty === "number") {
    if (player.fixture_difficulty <= 2) {
      reasons.push({ icon: "📅", text: "Favorable fixture" });
    } else if (player.fixture_difficulty >= 4) {
      reasons.push({ icon: "📅", text: "Tough fixture" });
    }
  } else if (
    typeof player.team_strength === "number" &&
    typeof player.opponent_strength === "number"
  ) {
    if (player.opponent_strength < player.team_strength) {
      reasons.push({ icon: "📅", text: "Favorable fixture" });
    } else if (player.opponent_strength > player.team_strength * 1.2) {
      reasons.push({ icon: "📅", text: "Tough fixture" });
    }
  }

  // Recent form
  if (
    typeof player.total_points_avg_last_3 === "number" &&
    typeof player.total_points_avg_last_10 === "number"
  ) {
    if (player.total_points_avg_last_3 > player.total_points_avg_last_10 * 1.2) {
      reasons.push({ icon: "🔥", text: "Form improving" });
    } else if (player.total_points_avg_last_3 < player.total_points_avg_last_10 * 0.7) {
      reasons.push({ icon: "📉", text: "Form dipping" });
    }
  } else if (typeof player.total_points_avg_last_3 === "number" && player.total_points_avg_last_3 >= 6) {
    reasons.push({ icon: "🔥", text: "In strong form" });
  }

  // Home advantage
  if (player.is_home === 1 || player.was_home === true) {
    reasons.push({ icon: "🏠", text: "Playing at home" });
  }

  // Haul potential from probabilities (only as a reason, not raw numbers)
  if (typeof player.prob_high_score_10 === "number" && player.prob_high_score_10 >= 0.15) {
    reasons.push({ icon: "🚀", text: "Haul potential" });
  } else if (typeof player.prob_high_score_6 === "number" && player.prob_high_score_6 >= 0.4) {
    reasons.push({ icon: "✨", text: "Good chance of a return" });
  }

  // Return top 4 reasons max
  return reasons.slice(0, 4);
}

/* ── Playing time description ──────────────────────────────────────── */

/**
 * Converts raw play probability / minutes into user-facing language.
 */
export function describePlayingChance(player: PlayerRecord): string | null {
  const playProb = player.predicted_p_play_60 ?? player.predicted_minutes_60_probability;
  const minutesAvg = player.minutes_avg_last_5 ?? player.minutes_avg_last_3;

  if (typeof playProb === "number") {
    if (playProb >= 0.85) return "Likely to start";
    if (playProb >= 0.6) return "Expected to play";
    if (playProb >= 0.4) return "Rotation risk";
    return "Unlikely to play";
  }

  if (typeof minutesAvg === "number") {
    if (minutesAvg >= 80) return "Nailed-on starter";
    if (minutesAvg >= 65) return "Regular starter";
    if (minutesAvg >= 45) return "Rotation risk";
    if (minutesAvg >= 20) return "Impact sub";
    return "Limited minutes";
  }

  return null;
}

/* ── Recommendation wording ────────────────────────────────────────── */

/**
 * Derives a short, honest recommendation label based on expected points
 * and confidence. Uses hedged language — never "guaranteed" or "must pick".
 */
export function deriveRecommendation(
  player: PlayerRecord,
  confidence: ConfidenceLevel,
): string {
  const xPts = player.predicted_expected_points ?? player.predicted_total_points;
  if (typeof xPts !== "number") return "Insufficient data";

  if (xPts >= 7 && confidence === "HIGH") return "Strong option this week";
  if (xPts >= 6 && confidence === "HIGH") return "Worth considering";
  if (xPts >= 7 && confidence === "MEDIUM") return "High ceiling pick";
  if (xPts >= 5 && confidence === "HIGH") return "Solid pick";
  if (xPts >= 5 && confidence === "MEDIUM") return "Decent option";
  if (xPts >= 4) return "Steady option";
  if (xPts >= 2) return "Low expected return";
  return "Unlikely to score well";
}

/* ── Legacy insight tags (improved labels) ─────────────────────────── */

/**
 * Derives short, honest insight tags STRICTLY from fields the backend
 * actually returned for this record. Nothing is fabricated: if a field is
 * absent, the insight it would produce is simply skipped.
 *
 * Labels now use football language instead of ML terminology.
 */
export function deriveInsights(player: PlayerRecord): Insight[] {
  const insights: Insight[] = [];

  if (typeof player.prob_high_score_10 === "number" && player.prob_high_score_10 >= 0.2) {
    insights.push({ label: "Haul potential", tone: "gold" });
  } else if (typeof player.prob_high_score_6 === "number" && player.prob_high_score_6 >= 0.4) {
    insights.push({ label: "Good return chance", tone: "gold" });
  }

  if (player.prediction_signals?.recent_form?.rating === "Elite") {
    insights.push({ label: "Excellent form", tone: "gold" });
  }

  if (player.prediction_signals?.attacking_threat?.rating === "High") {
    insights.push({ label: "Strong attacking threat", tone: "teal" });
  }

  if (
    typeof player.team_strength === "number" &&
    typeof player.opponent_strength === "number"
  ) {
    if (player.opponent_strength < player.team_strength) {
      insights.push({ label: "Favorable fixture", tone: "teal" });
    } else if (player.opponent_strength > player.team_strength) {
      insights.push({ label: "Tough fixture", tone: "coral" });
    }
  }

  if (
    typeof player.total_points_avg_last_3 === "number" &&
    typeof player.total_points_avg_last_10 === "number"
  ) {
    if (player.total_points_avg_last_3 > player.total_points_avg_last_10) {
      insights.push({ label: "Form improving", tone: "gold" });
    } else if (player.total_points_avg_last_3 < player.total_points_avg_last_10 * 0.7) {
      insights.push({ label: "Form dipping", tone: "coral" });
    }
  }

  if (typeof player.minutes_avg_last_5 === "number") {
    if (player.minutes_avg_last_5 >= 75) {
      insights.push({ label: "Consistent starter", tone: "signal" });
    } else if (player.minutes_avg_last_5 < 45) {
      insights.push({ label: "Limited minutes", tone: "coral" });
    }
  }

  if (player.is_home === 1 || player.was_home === true) {
    insights.push({ label: "Home advantage", tone: "neutral" });
  }

  if (typeof player.price_trend_last_5 === "number") {
    if (player.price_trend_last_5 > 0) {
      insights.push({ label: "Price rising", tone: "teal" });
    } else if (player.price_trend_last_5 < 0) {
      insights.push({ label: "Price falling", tone: "coral" });
    }
  }

  if (typeof player.rest_days === "number" && player.rest_days >= 6) {
    insights.push({ label: "Well rested", tone: "neutral" });
  }

  return insights;
}

/**
 * A simple, clearly-labeled reliability proxy derived from recent playing
 * time (NOT a true ML confidence score — the backend does not expose one).
 * Returns null when there isn't enough real data to derive it.
 */
export function derivePlayingTimeReliability(player: PlayerRecord): number | null {
  const minutes = player.minutes_avg_last_5 ?? player.minutes_avg_last_3;
  if (typeof minutes !== "number") return null;
  return Math.max(0, Math.min(1, minutes / 90));
}
