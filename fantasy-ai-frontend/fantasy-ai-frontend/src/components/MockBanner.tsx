import { FlaskConical } from "lucide-react";
import { isMockMode } from "@/api/mocks";

/**
 * Renders a persistent, unmissable banner whenever VITE_USE_MOCKS=true.
 * Mock mode must never be silent — this is the visual guarantee of that.
 */
export function MockBanner() {
  if (!isMockMode()) return null;
  return (
    <div className="flex items-center justify-center gap-2 border-b border-gold-border bg-gold-light px-4 py-2 text-xs font-black text-gold-dark shadow-xs">
      <FlaskConical size={14} className="text-gold-metallic" />
      <span>Mock data mode active — not connected to the live Fantasy Wizard backend.</span>
    </div>
  );
}
