import type { PlayerRecord } from "@/types/api";

export interface Insight {
  label: string;
  tone: "gold" | "signal" | "teal" | "coral" | "neutral";
}

/**
 * Derives short, honest insight tags STRICTLY from fields the backend
 * actually returned for this record. Nothing is fabricated: if a field is
 * absent, the insight it would produce is simply skipped. If no insights
 * can be derived at all, callers should show the "not enough data" empty
 * state rather than this function inventing something to fill the gap.
 */
export function deriveInsights(player: PlayerRecord): Insight[] {
  const insights: Insight[] = [];

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
      insights.push({ label: "High expected minutes", tone: "signal" });
    } else if (player.minutes_avg_last_5 < 45) {
      insights.push({ label: "Limited recent minutes", tone: "coral" });
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
