"use client";

import ThemeToggle from "@/components/ThemeToggle";
import HeroSection from "@/components/landing/HeroSection";
import TrustBar from "@/components/landing/TrustBar";
import StatsSection from "@/components/landing/StatsSection";
import FeatureCards from "@/components/landing/FeatureCards";

export default function Home() {
  return (
    <div className="flex flex-col">

      {/* ── Sticky header ─────────────────────────────────────────────────────
           z-[1002] keeps it above Leaflet's internal z-index: 1000 controls.
           bg-white/95 + backdrop-blur gives glass effect; dark mode handled
           via .dark .bg-white\/95 in globals.css.
      ──────────────────────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-[1002] flex shrink-0 items-center gap-3 border-b border-slate-200 bg-white/95 px-6 py-3 backdrop-blur-sm">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded bg-blue-600">
            <span className="text-xs font-bold text-white">AS</span>
          </div>
          <span className="text-base font-semibold tracking-tight text-slate-900">
            AutoSite
          </span>
        </div>
        <div className="h-4 w-px bg-slate-200" />
        <span className="hidden text-sm text-slate-500 sm:block">
          Toronto Site Pre-Acquisition Analysis
        </span>
        <div className="ml-auto flex items-center gap-2">
          <span className="hidden rounded border border-slate-200 px-2 py-1 text-xs text-slate-400 sm:inline">
            NVIDIA Spark Hack · May 2026
          </span>
          <ThemeToggle />
        </div>
      </header>

      {/* ── Landing sections ──────────────────────────────────────────────── */}
      {/* Hero: left=content, right=interactive map (desktop only).           */}
      <HeroSection />
      <TrustBar />
      <StatsSection />
      <FeatureCards />

      {/* ── Footer ────────────────────────────────────────────────────────── */}
      <footer className="border-t border-slate-800 bg-slate-950 px-6 py-10">
        <div className="mx-auto flex max-w-5xl flex-col items-center gap-3 text-center sm:flex-row sm:justify-between sm:text-left">
          <div className="flex items-center gap-2.5">
            <div className="flex h-6 w-6 items-center justify-center rounded bg-blue-600">
              <span className="text-[10px] font-bold text-white">AS</span>
            </div>
            <span className="text-sm font-semibold text-white">AutoSite</span>
            <span className="text-slate-600">·</span>
            <span className="text-sm text-slate-400">
              AI Co-Pilot for Toronto Real Estate
            </span>
          </div>
          <p className="text-xs text-slate-600">
            Built at NVIDIA Spark Hack Toronto 2026 · NVIDIA GB10 · LangGraph
          </p>
        </div>
      </footer>
    </div>
  );
}
