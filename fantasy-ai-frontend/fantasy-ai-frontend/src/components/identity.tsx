import { useState } from "react";
import { getInitials, getTeamCode, getTeamColor } from "@/lib/format";
import { cn } from "@/lib/utils";

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
          "shrink-0 rounded-full border-2 border-white bg-[#F1F5F9] object-cover shadow-sm",
          AVATAR_SIZES[size],
          className,
        )}
      />
    );
  }

  return (
    <div
      className={cn(
        "flex shrink-0 items-center justify-center rounded-full border-2 border-[#A7F3D0] bg-[#ECFDF5] font-display font-black text-[#059669] shadow-sm",
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
          className={cn("shrink-0 rounded-lg object-contain drop-shadow-sm", dim)}
        />
      ) : (
        <div
          className={cn("flex shrink-0 items-center justify-center rounded-lg font-black text-white shadow-sm", dim)}
          style={{ backgroundColor: color }}
          title={team ?? "Unknown team"}
        >
          {code}
        </div>
      )}
      {showName && (
        <span className="text-xs font-black text-[#0F172A]">{team ?? "N/A"}</span>
      )}
    </div>
  );
}
