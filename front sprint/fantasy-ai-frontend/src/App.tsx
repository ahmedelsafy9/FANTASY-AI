import { BrowserRouter, Routes, Route } from "react-router-dom";
import type { ReactNode } from "react";
import { Navigation } from "@/components/Navigation";
import { Footer } from "@/components/Footer";
import { MockBanner } from "@/components/MockBanner";
import Home from "@/pages/Home";
import Dashboard from "@/pages/Dashboard";
import Predictions from "@/pages/Predictions";
import Players from "@/pages/Players";
import PlayerDetails from "@/pages/PlayerDetails";
import Fixtures from "@/pages/Fixtures";
import About from "@/pages/About";

function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <MockBanner />
      <Navigation />
      <main className="flex-1">{children}</main>
      <Footer />
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout><Home /></Layout>} />
        <Route path="/dashboard" element={<Layout><Dashboard /></Layout>} />
        <Route path="/predictions" element={<Layout><Predictions /></Layout>} />
        <Route path="/players" element={<Layout><Players /></Layout>} />
        <Route path="/players/:id" element={<Layout><PlayerDetails /></Layout>} />
        <Route path="/fixtures" element={<Layout><Fixtures /></Layout>} />
        <Route path="/about" element={<Layout><About /></Layout>} />
      </Routes>
    </BrowserRouter>
  );
}
