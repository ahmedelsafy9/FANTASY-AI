import { getInitials, getTeamCode, getTeamColor } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * The backend does not provide player photo URLs or team badge images
 * (confirmed by inspecting `src/api/schemas.py` / the underlying dataset).
 * Rather than fabricate photos, both components render a deterministic,
 * stylized identity mark from the REAL name/team string — no invented data.
 */

interface PlayerAvatarProps {
  name: string | null | undefined;
  size?: "sm" | "md" | "lg";
  className?: string;
}

const AVATAR_SIZES: Record<string, string> = {
  sm: "h-8 w-8 text-xs",
  md: "h-11 w-11 text-sm",
  lg: "h-16 w-16 text-lg",
};

export function PlayerAvatar({ name, size = "md", className }: PlayerAvatarProps) {
  return (
    <div
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full border border-border-medium bg-gradient-to-br from-surface-elevated to-surface font-display font-semibold text-ink-secondary",
        AVATAR_SIZES[size],
        className,
      )}
      aria-hidden="true"
    >
      {getInitials(name)}
    </div>
  );
}

interface TeamBadgeProps {
  team: string | null | undefined;
  size?: "sm" | "md";
  showName?: boolean;
  className?: string;
}

export function TeamBadge({ team, size = "sm", showName = false, className }: TeamBadgeProps) {
  const color = getTeamColor(team);
  const code = getTeamCode(team);
  const dim = size === "sm" ? "h-6 w-6 text-[10px]" : "h-8 w-8 text-xs";

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div
        className={cn("flex shrink-0 items-center justify-center rounded-md font-bold text-void", dim)}
        style={{ backgroundColor: color }}
        title={team ?? "Unknown team"}
      >
        {code}
      </div>
      {showName && (
        <span className="text-sm text-ink-secondary">{team ?? "N/A"}</span>
      )}
    </div>
  );
}
