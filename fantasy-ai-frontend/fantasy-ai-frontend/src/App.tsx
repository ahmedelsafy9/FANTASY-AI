import { BrowserRouter, Routes, Route } from "react-router-dom";
import type { ReactNode } from "react";
import { AuthProvider } from "@/context/AuthContext";
import { Navigation } from "@/components/Navigation";
import { Footer } from "@/components/Footer";
import { MockBanner } from "@/components/MockBanner";
import { LoginModal } from "@/components/LoginModal";
import { AuthToast } from "@/components/Toast";
import Home from "@/pages/Home";
import Dashboard from "@/pages/Dashboard";
import Predictions from "@/pages/Predictions";
import Players from "@/pages/Players";
import PlayerDetails from "@/pages/PlayerDetails";
import Fixtures from "@/pages/Fixtures";
import Squad from "@/pages/Squad";
import Captain from "@/pages/Captain";

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
          <Route path="/" element={<Layout><Home /></Layout>} />
          <Route path="/dashboard" element={<Layout><Dashboard /></Layout>} />
          <Route path="/predictions" element={<Layout><Predictions /></Layout>} />
          <Route path="/players" element={<Layout><Players /></Layout>} />
          <Route path="/players/:id" element={<Layout><PlayerDetails /></Layout>} />
          <Route path="/fixtures" element={<Layout><Fixtures /></Layout>} />
          <Route path="/squad" element={<Layout><Squad /></Layout>} />
          <Route path="/captain" element={<Layout><Captain /></Layout>} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
