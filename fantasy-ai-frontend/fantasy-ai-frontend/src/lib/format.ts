/**
 * Formats a player price. The backend stores price as an integer using
 * FPL's own convention (price x10, e.g. 129 => £12.9m) — this simply
 * renders that convention; it never invents a price when one is absent.
 */
export function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  return `£${(value / 10).toFixed(1)}m`;
}

/** Formats a points/stat number to whole number (nearest integer), or "N/A" if absent. */
export function formatStat(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  if (digits === 0) return String(Math.round(value));
  return value.toFixed(digits);
}

/** Formats an integer count, or "N/A" if absent. */
export function formatInt(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  return String(Math.round(value));
}

/**
 * Formats expected points for display as whole number: e.g. "7 pts".
 * Rounds to the nearest integer. Never displays decimal places in prediction numbers.
 */
export function formatExpectedPoints(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "— pts";
  return `${Math.round(value)} pts`;
}

/**
 * Returns the expected points as just the whole number for prominent display (e.g. "7").
 */
export function formatExpectedPointsNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return String(Math.round(value));
}

/**
 * Formats a probability or percentage to the nearest whole percentage point (e.g. "73%").
 */
export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—%";
  const pct = value <= 1.0 && value >= 0.0 ? value * 100 : value;
  return `${Math.round(pct)}%`;
}

/** Extracts up to 2 initials from a player's display name. */
export function getInitials(name: string | null | undefined): string {
  if (!name) return "??";
  const parts = name.replace(/\./g, " ").trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "??";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/** Extracts up to 3 letters for a team badge from a team's real name. */
export function getTeamCode(team: string | null | undefined): string {
  if (!team) return "—";
  const cleaned = team.replace(/[^a-zA-Z ]/g, "").trim();
  const words = cleaned.split(/\s+/).filter(Boolean);
  if (words.length === 1) return words[0].slice(0, 3).toUpperCase();
  return words.map((w) => w[0]).join("").slice(0, 3).toUpperCase();
}

/**
 * A small, curated palette (not "random colors") used to deterministically
 * color-code team badges by hashing the team's real name — the same team
 * always gets the same color, and no color is chosen arbitrarily per
 * render.
 */
const TEAM_PALETTE = [
  "#7C86FF",
  "#34D1B8",
  "#E8B85C",
  "#E5695A",
  "#5FB0E8",
  "#C88CF0",
  "#5FD98A",
  "#F0A15F",
];

export function getTeamColor(team: string | null | undefined): string {
  if (!team) return "#626B76";
  let hash = 0;
  for (let i = 0; i < team.length; i++) {
    hash = (hash << 5) - hash + team.charCodeAt(i);
    hash |= 0;
  }
  return TEAM_PALETTE[Math.abs(hash) % TEAM_PALETTE.length];
}
