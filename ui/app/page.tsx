"use client";

import dynamic from "next/dynamic";
import ThemeToggle from "@/components/ThemeToggle";
import HeroSection from "@/components/landing/HeroSection";
import StatsSection from "@/components/landing/StatsSection";
import FeatureCards from "@/components/landing/FeatureCards";

// Used only in the mobile map fallback section below.
const ParcelMap = dynamic(() => import("@/components/ParcelMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center bg-slate-100">
      <p className="text-sm text-slate-500">Loading map…</p>
    </div>
  ),
});

export default function Home() {
  return (
    <div className="flex flex-col">

      {/* ── Sticky header ─────────────────────────────────────────────────────
           z-[1002] sits above Leaflet's internal z-index: 1000 controls.
           Dark-mode bg handled via .dark .bg-white\/95 in globals.css.
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
            NVIDIA GB10 · Toronto
          </span>
          <ThemeToggle />
        </div>
      </header>

      {/* ── Hero: left = search + copy, right = compact map (desktop only) ── */}
      <HeroSection />

      {/* ── Mobile map fallback ────────────────────────────────────────────
           On desktop the map lives inside HeroSection. This section gives
           mobile users direct access to the interactive map.
      ──────────────────────────────────────────────────────────────────── */}
      <section id="map-section" className="bg-white px-6 py-16 lg:hidden">
        <div className="mx-auto max-w-2xl">
          <div className="mb-6 text-center">
            <h2 className="text-2xl font-bold tracking-tight text-slate-900">
              Click any Toronto parcel
            </h2>
            <p className="mt-2 text-sm text-slate-500">
              Your complete development brief is ready in about 60 seconds.
            </p>
          </div>
          <div
            className="overflow-hidden rounded-2xl border border-slate-200 shadow-lg"
            style={{ height: 420 }}
          >
            <ParcelMap />
          </div>
        </div>
      </section>

      {/* ── Feature cards, then stats as proof ───────────────────────────── */}
      <FeatureCards />
      <StatsSection />

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
            Powered by NVIDIA GB10 · LangGraph · Toronto 2026
          </p>
        </div>
      </footer>
    </div>
  );
}
