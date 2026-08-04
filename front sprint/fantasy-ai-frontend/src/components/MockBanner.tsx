import { FlaskConical } from "lucide-react";
import { isMockMode } from "@/api/mocks";

/**
 * Renders a persistent, unmissable banner whenever VITE_USE_MOCKS=true.
 * Mock mode must never be silent — this is the visual guarantee of that.
 */
export function MockBanner() {
  if (!isMockMode()) return null;
  return (
    <div className="flex items-center justify-center gap-2 border-b border-gold/30 bg-gold/10 px-4 py-2 text-xs font-medium text-gold">
      <FlaskConical size={13} />
      Mock data mode — not connected to the real Fantasy-AI backend.
    </div>
  );
}
