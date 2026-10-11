import type { PlayerRecord } from "@/types/api";

export type AvailabilityState =
  | "available"
  | "doubtful"
  | "injured"
  | "suspended"
  | "unavailable"
  | "unknown";

export interface AvailabilityInfo {
  state: AvailabilityState;
  label: string;
  shortLabel: string;
  chancePct: number | null;
  news: string | null;
}

/**
 * Derives player availability deterministically from official FPL API fields.
 * Never guesses from player form or predicted points.
 */
export function derivePlayerAvailability(player: PlayerRecord): AvailabilityInfo {
  const status = (player.status as string | undefined)?.toLowerCase();
  const availabilityStatus = (player.availability_status as string | undefined)?.toLowerCase();
  const injuryFlag = Boolean(player.injury_flag);
  const doubtFlag = Boolean(player.doubt_flag);
  const suspensionFlag = Boolean(player.suspension_flag);
  const ruledOutFlag = Boolean(player.ruled_out_flag);
  const chance =
    typeof player.chance_of_playing_next_round === "number"
      ? player.chance_of_playing_next_round
      : typeof player.chance_of_playing_this_round === "number"
      ? player.chance_of_playing_this_round
      : null;
  const news = (player.team_news as string | null | undefined) ?? null;

  // 1. Suspension
  if (status === "s" || availabilityStatus === "suspended" || suspensionFlag) {
    return {
      state: "suspended",
      label: "Suspended",
      shortLabel: "Susp",
      chancePct: chance,
      news,
    };
  }

  // 2. Ruled out / unavailable
  if (
    status === "u" ||
    status === "n" ||
    availabilityStatus === "ruled_out" ||
    availabilityStatus === "unavailable" ||
    ruledOutFlag ||
    chance === 0
  ) {
    return {
      state: "unavailable",
      label: "Unavailable",
      shortLabel: "Out",
      chancePct: 0,
      news,
    };
  }

  // 3. Injury
  if (
    status === "i" ||
    availabilityStatus === "minor_injury" ||
    availabilityStatus === "major_injury" ||
    injuryFlag
  ) {
    return {
      state: "injured",
      label: "Injured",
      shortLabel: "Inj",
      chancePct: chance,
      news,
    };
  }

  // 4. Doubtful (flags or 25% / 50% / 75% chance)
  if (
    status === "d" ||
    availabilityStatus === "doubtful" ||
    doubtFlag ||
    (chance !== null && chance > 0 && chance < 100)
  ) {
    const chanceText = chance !== null ? ` (${chance}%)` : "";
    return {
      state: "doubtful",
      label: `Doubtful${chanceText}`,
      shortLabel: chance !== null ? `${chance}%` : "Doubt",
      chancePct: chance,
      news,
    };
  }

  // 5. Explicitly available
  if (status === "a" || availabilityStatus === "fit") {
    return {
      state: "available",
      label: "Available",
      shortLabel: "Fit",
      chancePct: 100,
      news: null,
    };
  }

  // 6. If no official status fields exist in record
  if (!status && !availabilityStatus && chance === null) {
    return {
      state: "unknown",
      label: "Status Pending",
      shortLabel: "Pending",
      chancePct: null,
      news: null,
    };
  }

  // Default fallback for unrecognized non-empty value
  return {
    state: "available",
    label: "Available",
    shortLabel: "Fit",
    chancePct: chance ?? 100,
    news,
  };
}
