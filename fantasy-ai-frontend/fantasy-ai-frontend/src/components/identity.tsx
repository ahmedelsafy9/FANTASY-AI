import { useState } from "react";
import { getInitials, getTeamCode, getTeamColor } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * Phase 5 update: the backend can now optionally provide real player photo
 * and team badge URLs (built server-side from live FPL API fields — see
 * the backend's `src/metadata/` package). When present, those are used;
 * when absent (or the image fails to load), both components fall back to
 * the original deterministic initials/color mark — never a fabricated
 * image, and the same honest behavior as before this update.
 */

interface PlayerAvatarProps {
  name: string | null | undefined;
  photoUrl?: string | null;
  size?: "sm" | "md" | "lg" | "xl";
  className?: string;
}

const AVATAR_SIZES: Record<string, string> = {
  sm: "h-8 w-8 text-xs",
  md: "h-11 w-11 text-sm",
  lg: "h-16 w-16 text-lg",
  xl: "h-24 w-24 text-2xl",
};

export function PlayerAvatar({ name, photoUrl, size = "md", className }: PlayerAvatarProps) {
  const [imgFailed, setImgFailed] = useState(false);

  if (photoUrl && !imgFailed) {
    return (
      <img
        src={photoUrl}
        alt={name ?? "Player photo"}
        onError={() => setImgFailed(true)}
        className={cn(
          "shrink-0 rounded-full border border-border-medium bg-surface-elevated object-cover",
          AVATAR_SIZES[size],
          className,
        )}
      />
    );
  }

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
  logoUrl?: string | null;
  size?: "sm" | "md" | "lg";
  showName?: boolean;
  className?: string;
}

export function TeamBadge({ team, logoUrl, size = "sm", showName = false, className }: TeamBadgeProps) {
  const [imgFailed, setImgFailed] = useState(false);
  const color = getTeamColor(team);
  const code = getTeamCode(team);
  const dim = size === "sm" ? "h-6 w-6 text-[10px]" : size === "md" ? "h-8 w-8 text-xs" : "h-10 w-10 text-sm";

  return (
    <div className={cn("flex items-center gap-2", className)}>
      {logoUrl && !imgFailed ? (
        <img
          src={logoUrl}
          alt={team ?? "Team badge"}
          onError={() => setImgFailed(true)}
          className={cn("shrink-0 rounded-md object-contain", dim)}
        />
      ) : (
        <div
          className={cn("flex shrink-0 items-center justify-center rounded-md font-bold text-void", dim)}
          style={{ backgroundColor: color }}
          title={team ?? "Unknown team"}
        >
          {code}
        </div>
      )}
      {showName && (
        <span className="text-sm text-ink-secondary">{team ?? "N/A"}</span>
      )}
    </div>
  );
}
