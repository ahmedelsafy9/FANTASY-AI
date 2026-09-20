import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import type { ReactNode } from "react";
import { AuthProvider } from "@/context/AuthContext";
import { Navigation } from "@/components/Navigation";
import { Footer } from "@/components/Footer";
import { MockBanner } from "@/components/MockBanner";
import { LoginModal } from "@/components/LoginModal";
import { AuthToast } from "@/components/Toast";
import Home from "@/pages/Home";
import Players from "@/pages/Players";
import PlayerDetails from "@/pages/PlayerDetails";
import Squad from "@/pages/Squad";
import Captain from "@/pages/Captain";
import MatchPredictions from "@/pages/MatchPredictions";
import Differentials from "@/pages/Differentials";

function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-[#e5e7eb]">
      <MockBanner />
      <Navigation />
      <main className="flex-1 pb-safe-bottom md:pb-0">{children}</main>
      <Footer />
      <LoginModal />
      <AuthToast />
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Primary Redesigned Routes */}
          <Route path="/" element={<Layout><Home /></Layout>} />
          <Route path="/players" element={<Layout><Players /></Layout>} />
          <Route path="/players/:id" element={<Layout><PlayerDetails /></Layout>} />
          <Route path="/captain" element={<Layout><Captain /></Layout>} />
          <Route path="/differentials" element={<Layout><Differentials /></Layout>} />
          <Route path="/match-predictions" element={<Layout><MatchPredictions /></Layout>} />
          <Route path="/squad" element={<Layout><Squad /></Layout>} />

          {/* Compatibility Redirects (Preserve bookmarks and old links) */}
          <Route path="/dashboard" element={<Navigate to="/" replace />} />
          <Route path="/predictions" element={<Navigate to="/players" replace />} />
          <Route path="/fixtures" element={<Navigate to="/match-predictions" replace />} />

          {/* Catch-all fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
