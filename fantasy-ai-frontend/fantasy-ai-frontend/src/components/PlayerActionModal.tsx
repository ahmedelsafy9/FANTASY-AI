import { AnimatePresence, motion } from "framer-motion";
import {
  Crown,
  Shield,
  ArrowUpDown,
  RefreshCw,
  Info,
  Trash2,
  X,
} from "lucide-react";
import type { PlayerRecord } from "@/types/api";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { FixtureBadge } from "@/components/FixtureBadge";
import { formatPrice, formatInt } from "@/lib/format";
import { normalizePosition } from "@/hooks/useSquad";

interface PlayerActionModalProps {
  player: PlayerRecord | null;
  isStarter: boolean;
  isCaptain: boolean;
  isViceCaptain: boolean;
  onClose: () => void;
  onMakeCaptain: () => void;
  onMakeViceCaptain: () => void;
  onStartSwap: () => void;
  onReplace: () => void;
  onViewDetails: () => void;
  onRemove: () => void;
}

export function PlayerActionModal({
  player,
  isStarter,
  isCaptain,
  isViceCaptain,
  onClose,
  onMakeCaptain,
  onMakeViceCaptain,
  onStartSwap,
  onReplace,
  onViewDetails,
  onRemove,
}: PlayerActionModalProps) {
  if (!player) return null;

  const pos = normalizePosition(player.position);
  const posLabel =
    pos === "GKP"
      ? "Goalkeeper"
      : pos === "DEF"
        ? "Defender"
        : pos === "MID"
          ? "Midfielder"
          : "Forward";

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="absolute inset-0 bg-[#0F172A]/50 backdrop-blur-xs"
          onClick={onClose}
          aria-hidden="true"
        />

        {/* Modal Card */}
        <motion.div
          role="dialog"
          aria-modal="true"
          initial={{ opacity: 0, scale: 0.95, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 10 }}
          transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
          className="relative z-10 w-full max-w-sm overflow-hidden rounded-chunky-xl border border-[#E8E3ED] bg-white p-0 text-[#19171D] shadow-xl"
        >
          {/* Header Bar */}
          <div className="relative bg-gradient-to-br from-[#452477] via-[#381B62] to-[#250F43] p-5 text-white">
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="absolute right-3.5 top-3.5 rounded-full bg-white/10 p-1.5 text-white/80 transition-colors hover:bg-white/20 hover:text-white cursor-pointer"
            >
              <X size={16} />
            </button>

            <div className="flex items-center gap-3.5">
              <div className="relative">
                <PlayerAvatar
                  name={player.name}
                  photoUrl={player.photo_url}
                  size="lg"
                  className="ring-3 ring-white/80 shadow-md"
                />
                {isCaptain && (
                  <div
                    className="absolute -left-1.5 -top-1.5 flex h-6 w-6 items-center justify-center rounded-full bg-[#B58A18] text-xs font-black text-white shadow-md border-2 border-white"
                    title="Current Captain"
                  >
                    C
                  </div>
                )}
                {!isCaptain && isViceCaptain && (
                  <div
                    className="absolute -left-1.5 -top-1.5 flex h-6 w-6 items-center justify-center rounded-full bg-[#B9DDF5] text-xs font-black text-[#19171D] shadow-md border-2 border-white"
                    title="Current Vice-Captain"
                  >
                    VC
                  </div>
                )}
              </div>

              <div className="min-w-0 flex-1">
                <h3 className="truncate font-display text-lg font-black text-white leading-tight">
                  {player.name ?? "Player"}
                </h3>
                <div className="mt-1 flex flex-wrap items-center gap-1.5">
                  <TeamBadge team={player.team} logoUrl={player.team_logo_url} size="sm" />
                  <span className="rounded bg-white/20 px-1.5 py-0.5 text-[10px] font-black uppercase text-white">
                    {posLabel}
                  </span>
                  <span className="rounded bg-[#EEE7FA]/20 border border-[#EEE7FA]/30 px-1.5 py-0.5 text-[10px] font-black text-[#EEE7FA]">
                    {isStarter ? "Starting XI" : "Substitute"}
                  </span>
                </div>
              </div>
            </div>

            {/* Quick stats banner */}
            <div className="mt-4 grid grid-cols-3 gap-2 rounded-xl bg-white/10 p-2.5 text-center backdrop-blur-xs border border-white/10">
              <div>
                <span className="text-[9px] font-black uppercase text-white/70 block">
                  Price
                </span>
                <span className="text-xs font-black text-white numeral">
                  {formatPrice(player.value)}
                </span>
              </div>
              <div>
                <span className="text-[9px] font-black uppercase text-[#B9DDF5] block">
                  AI xPts
                </span>
                <span className="text-xs font-black text-[#B9DDF5] numeral">
                  {formatInt(player.predicted_total_points)}
                  {isCaptain && (
                    <span className="text-[9px] text-white/80 ml-0.5">(2×={formatInt((player.predicted_total_points ?? 0) * 2)})</span>
                  )}
                </span>
              </div>
              <div>
                <span className="text-[9px] font-black uppercase text-white/70 block">
                  Next Match
                </span>
                <div className="flex justify-center mt-0.5">
                  <FixtureBadge player={player} size="sm" />
                </div>
              </div>
            </div>
          </div>

          {/* Action List */}
          <div className="flex flex-col gap-1.5 p-4">
            {/* Captain & VC buttons (Starters only) */}
            {isStarter && (
              <div className="grid grid-cols-2 gap-2 mb-1">
                <button
                  type="button"
                  onClick={() => {
                    onMakeCaptain();
                    onClose();
                  }}
                  disabled={isCaptain}
                  className={`flex items-center justify-center gap-1.5 rounded-xl border py-2.5 px-3 text-xs font-black transition-all cursor-pointer ${
                    isCaptain
                      ? "bg-[#FDF8EC] border-[#E5D08E] text-[#8C680E] font-extrabold cursor-default opacity-80"
                      : "bg-white border-[#E5D08E] text-[#8C680E] hover:bg-[#FDF8EC] shadow-sm"
                  }`}
                >
                  <Crown size={15} className="text-[#B58A18]" />
                  <span>{isCaptain ? "Captain (C)" : "Make Captain"}</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    onMakeViceCaptain();
                    onClose();
                  }}
                  disabled={isViceCaptain}
                  className={`flex items-center justify-center gap-1.5 rounded-xl border py-2.5 px-3 text-xs font-black transition-all cursor-pointer ${
                    isViceCaptain
                      ? "bg-[#EEF7FC] border-[#B9DDF5] text-[#1E4D6B] font-extrabold cursor-default opacity-80"
                      : "bg-white border-[#B9DDF5] text-[#1E4D6B] hover:bg-[#EEF7FC] shadow-sm"
                  }`}
                >
                  <Shield size={15} className="text-[#1E4D6B]" />
                  <span>{isViceCaptain ? "Vice-Cap (VC)" : "Make Vice-Cap"}</span>
                </button>
              </div>
            )}

            {/* Substitute / Swap Button */}
            <button
              type="button"
              onClick={() => {
                onStartSwap();
                onClose();
              }}
              className="flex w-full items-center justify-between rounded-xl border border-[#E8E3ED] bg-white p-3 text-left text-xs font-black text-[#19171D] shadow-sm transition-all hover:border-[#7041C5] hover:bg-[#EEE7FA]/30 hover:text-[#452477] cursor-pointer group"
            >
              <div className="flex items-center gap-2.5">
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#EEE7FA] text-[#452477] group-hover:bg-[#7041C5] group-hover:text-white transition-colors">
                  <ArrowUpDown size={15} />
                </div>
                <div>
                  <span className="block font-black">Substitute / Swap</span>
                  <span className="block text-[10px] font-medium text-[#6F6A76]">
                    Swap with a player on the pitch or bench
                  </span>
                </div>
              </div>
            </button>

            {/* Replace Player (Transfer) Button */}
            <button
              type="button"
              onClick={() => {
                onReplace();
                onClose();
              }}
              className="flex w-full items-center justify-between rounded-xl border border-[#E8E3ED] bg-white p-3 text-left text-xs font-black text-[#19171D] shadow-sm transition-all hover:border-[#7041C5] hover:bg-[#EEE7FA]/30 hover:text-[#452477] cursor-pointer group"
            >
              <div className="flex items-center gap-2.5">
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#EEE7FA] text-[#452477] group-hover:bg-[#7041C5] group-hover:text-white transition-colors">
                  <RefreshCw size={15} />
                </div>
                <div>
                  <span className="block font-black">Replace Player</span>
                  <span className="block text-[10px] font-medium text-[#6F6A76]">
                    Choose a direct {posLabel} replacement
                  </span>
                </div>
              </div>
            </button>

            {/* View Full Details Button */}
            <button
              type="button"
              onClick={() => {
                onViewDetails();
                onClose();
              }}
              className="flex w-full items-center justify-between rounded-xl border border-[#E8E3ED] bg-white p-3 text-left text-xs font-black text-[#19171D] shadow-sm transition-all hover:bg-[#F8F7FA] cursor-pointer group"
            >
              <div className="flex items-center gap-2.5">
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#F4F3F6] text-[#6F6A76] group-hover:bg-[#452477] group-hover:text-white transition-colors">
                  <Info size={15} />
                </div>
                <div>
                  <span className="block font-black">Player Details & Analytics</span>
                  <span className="block text-[10px] font-medium text-[#6F6A76]">
                    View form trends, fixture metrics & AI breakdown
                  </span>
                </div>
              </div>
            </button>

            {/* Remove Player Button */}
            <button
              type="button"
              onClick={() => {
                onRemove();
                onClose();
              }}
              className="mt-1 flex w-full items-center justify-center gap-2 rounded-xl border border-red-200 bg-red-50/60 py-2.5 text-xs font-black text-red-600 hover:bg-red-100 hover:text-red-700 transition-colors cursor-pointer"
            >
              <Trash2 size={14} />
              <span>Remove from Squad</span>
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
