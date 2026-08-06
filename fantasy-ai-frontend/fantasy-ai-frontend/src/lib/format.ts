/**
 * Formats a player price. The backend stores price as an integer using
 * FPL's own convention (price x10, e.g. 129 => £12.9m) — this simply
 * renders that convention; it never invents a price when one is absent.
 */
export function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  return `£${(value / 10).toFixed(1)}m`;
}

/** Formats a points/stat number to one decimal place, or "N/A" if absent. */
export function formatStat(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  return value.toFixed(digits);
}

/** Formats an integer count, or "N/A" if absent. */
export function formatInt(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  return String(Math.round(value));
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
